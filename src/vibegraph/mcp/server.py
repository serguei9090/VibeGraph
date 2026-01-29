import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

from vibegraph.indexer.db import IndexerDB
from vibegraph.indexer.main import reindex_all

mcp = FastMCP("VibeGraph")


def _get_db() -> IndexerDB:
    return IndexerDB()


def _normalize_path(file_path: str) -> str:
    """Normalize file path to match DB storage format (absolute, resolved)."""
    return str(Path(file_path).resolve())


@mcp.tool()
def get_structural_summary(file_path: str, limit: int = 100, offset: int = 0) -> str:
    """
    Get a concise structural summary of a file (classes, functions, methods).

    Args:
        file_path: Path to the file to analyze
        limit: Maximum number of nodes to return (default: 100)
        offset: Number of nodes to skip for pagination (default: 0)
    """
    normalized_path = _normalize_path(file_path)
    db = _get_db()
    with db._get_conn() as conn:
        # Get total count
        count_cursor = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE file_path = ?", (normalized_path,)
        )
        total = count_cursor.fetchone()[0]

        # Get paginated results
        cursor = conn.execute(
            """SELECT name, kind, signature, start_line, end_line 
               FROM nodes 
               WHERE file_path = ? 
               ORDER BY start_line
               LIMIT ? OFFSET ?""",
            (normalized_path, limit, offset),
        )
        rows = cursor.fetchall()

    if total == 0:
        return f"No structure schema found for {file_path} (File might not be indexed)."

    # Format output with pagination info
    end_idx = min(offset + len(rows), total)
    summary = [
        f"Structure for {normalized_path} (showing {offset + 1}-{end_idx} of {total} nodes):\n"
    ]

    for row in rows:
        prefix = "- "
        info = f"{prefix}[{row['kind']}] {row['name']}"
        if row["signature"]:
            info += f"{row['signature']}"
        info += f" (L{row['start_line']}-{row['end_line']})"
        summary.append(info)

    # Add pagination hint if there are more results
    if end_idx < total:
        remaining = total - end_idx
        next_offset = offset + limit
        summary.append(
            f"\n... {remaining} more nodes available (use offset={next_offset} to see more)"
        )

    return "\n".join(summary)


class GraphTraverser:
    def __init__(self, db: IndexerDB):
        self.db = db
        self.visited: set[str] = set()
        self.output: list[str] = []

    def traverse(
        self,
        current_id: str,
        depth: int,
        max_depth: int,
        direction: Literal["up", "down"],
        indent: int,
        conn,
    ):
        if depth > max_depth:
            return

        # Check for cycles
        if current_id in self.visited:
            self.output.append(f"{'  ' * indent}🔄 [CYCLE DETECTED - circular dependency]")
            return

        self.visited.add(current_id)

        if direction == "up":
            # callers: edges where to_node_id = current_id
            query = """
                SELECT e.from_node_id as neighbor_id, e.relation_type, n.name, n.file_path 
                FROM edges e
                JOIN nodes n ON e.from_node_id = n.id
                WHERE e.to_node_id = ?
            """
            prefix = "← called by"
        else:
            # callees: edges where from_node_id = current_id
            query = """
                SELECT e.to_node_id as neighbor_id, e.relation_type, n.name, n.file_path 
                FROM edges e
                JOIN nodes n ON e.to_node_id = n.id
                WHERE e.from_node_id = ?
            """
            prefix = "→ calls"

        cursor = conn.execute(query, (current_id,))
        neighbors = cursor.fetchall()

        for n in neighbors:
            line = (
                f"{'  ' * indent}- {prefix} `{n['name']}` ({n['relation_type']}) "
                f"in `{n['file_path']}`"
            )
            self.output.append(line)
            self.traverse(n["neighbor_id"], depth + 1, max_depth, direction, indent + 1, conn)


@mcp.tool()
def get_call_stack(
    node_name: str, file_path: str | None = None, direction: str = "both", depth: int = 1
) -> str:
    """
    Trace function calls up (callers) or down (callees).
    """
    db = _get_db()
    with db._get_conn() as conn:
        query = "SELECT id, name, file_path, kind FROM nodes WHERE name = ?"
        params = [node_name]
        if file_path:
            query += " AND file_path = ?"
            params.append(_normalize_path(file_path))

        cursor = conn.execute(query, tuple(params))
        start_nodes = cursor.fetchall()

        if not start_nodes:
            return f"Node '{node_name}' not found."

        traverser = GraphTraverser(db)

        for start_node in start_nodes:
            traverser.output.append(
                f"### Trace for `{start_node['name']}` ({start_node['kind']}) "
                f"in `{start_node['file_path']}`"
            )

            if direction in ("up", "both"):
                traverser.output.append("\n**Callers (Incoming):**")
                traverser.traverse(start_node["id"], 1, depth, "up", 0, conn)
                traverser.visited.clear()

            if direction in ("down", "both"):
                traverser.output.append("\n**Callees (Outgoing):**")
                traverser.traverse(start_node["id"], 1, depth, "down", 0, conn)

    return "\n".join(traverser.output)


@mcp.tool()
def impact_analysis(file_path: str) -> str:
    """
    Analyze what other files/functions break if this file is modified.
    """
    normalized_path = _normalize_path(file_path)
    db = _get_db()
    with db._get_conn() as conn:
        cursor = conn.execute("SELECT id, name FROM nodes WHERE file_path = ?", (normalized_path,))
        file_nodes = cursor.fetchall()

        if not file_nodes:
            return f"No nodes found in {file_path}. Is it indexed?"

        output = [f"## Impact Analysis for `{normalized_path}`"]
        output.append("If you modify this file, the following components depend on it:\n")

        total_impact = 0

        for node in file_nodes:
            query = """
                SELECT DISTINCT n.file_path, n.name, e.relation_type
                FROM edges e
                JOIN nodes n ON e.from_node_id = n.id
                WHERE e.to_node_id = ? AND n.file_path != ?
            """
            cursor = conn.execute(query, (node["id"], normalized_path))
            dependents = cursor.fetchall()

            if dependents:
                output.append(f"- **`{node['name']}`** is used by:")
                for dep in dependents:
                    output.append(
                        f"  - `{dep['name']}` in `{dep['file_path']}` ({dep['relation_type']})"
                    )
                total_impact += len(dependents)

        if total_impact == 0:
            output.append("No external dependencies found (Safe to refactor?).")

    return "\n".join(output)


@mcp.tool()
def reindex_project(path: str = ".") -> str:
    """
    Reindex a file or directory recursively.
    Use "." for the current project root.
    """
    db = _get_db()
    try:
        with redirect_stdout(sys.stderr):
            reindex_all(
                db, path, verbose=True
            )  # Now we can even leave it True since it goes to stderr!
        return f"Successfully reindexed: {path}"
    except Exception as e:
        return f"Error during reindexing: {e}"


def main():
    """Entry point for the vibegraph-mcp console script."""
    mcp.run()


if __name__ == "__main__":
    main()
