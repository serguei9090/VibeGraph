"""
VibeGraph MCP Server - Code Intelligence Tools.

This server provides tools to analyze and understand codebases through
structural parsing (Tree-sitter) and a relational database (SQLite).
"""

import os
import sys
from contextlib import redirect_stdout
from enum import Enum
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from vibegraph.indexer.db import IndexerDB
from vibegraph.indexer.main import reindex_all

# Initialize the MCP server with proper naming convention
mcp = FastMCP("vibegraph_mcp")


# =============================================================================
# Shared Utilities
# =============================================================================


def _get_context_for_path(path_hint: str | None = None) -> tuple[IndexerDB, Path]:
    """
    Determine the project root and database connection for a given path.

    It searches upwards from the path_hint (or CWD if None) for markers:
    .git, pyproject.toml, or vibegraph_context.
    """
    if not path_hint or path_hint == ".":
        search_start = Path.cwd()
    else:
        search_start = Path(path_hint).resolve()

    search_dir = search_start if search_start.is_dir() else search_start.parent
    project_root = search_dir

    # Traverse up for markers
    for parent in [search_dir, *list(search_dir.parents)]:
        if (
            (parent / ".git").exists()
            or (parent / "pyproject.toml").exists()
            or (parent / "vibegraph_context").exists()
        ):
            project_root = parent
            break

    context_dir = project_root / "vibegraph_context"
    context_dir.mkdir(exist_ok=True)
    db_path = context_dir / "vibegraph.db"

    return IndexerDB(db_path=str(db_path)), project_root


def _normalize_path(file_path: str, project_root: Path) -> str:
    """Normalize file path relative to the identified project root."""
    try:
        return str(Path(file_path).resolve().relative_to(project_root))
    except (ValueError, RuntimeError):
        # Fallback if path is not in project root
        return str(Path(file_path).resolve())


def _safe_str(s: str) -> str:
    """Safely format string for output, replacing emojis on Windows if needed."""
    if os.name != "nt":
        return s

    # Simple replacement map for common emojis used in this file
    replacements = {
        "🔄": "[CYCLE]",
        "←": "<-",
        "→": "->",
        "✅": "[OK]",
    }
    for char, replacement in replacements.items():
        s = s.replace(char, replacement)
    return s


def _handle_error(e: Exception, context: str = "") -> str:
    """Consistent error formatting across all tools."""
    error_type = type(e).__name__
    if context:
        return f"Error ({error_type}): {context} - {e}"
    return f"Error ({error_type}): {e}"


# =============================================================================
# Enums
# =============================================================================


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    MARKDOWN = "markdown"
    JSON = "json"


class TraceDirection(str, Enum):
    """Direction for call stack tracing."""

    UP = "up"
    DOWN = "down"
    BOTH = "both"


# =============================================================================
# Pydantic Input Models
# =============================================================================


class StructuralSummaryInput(BaseModel):
    """Input model for structural summary operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_path: str = Field(
        ...,
        description="Path to the file to analyze (e.g., 'src/parser.py')",
        min_length=1,
    )
    limit: int = Field(
        default=100,
        description="Maximum number of nodes to return",
        ge=1,
        le=500,
    )
    offset: int = Field(
        default=0,
        description="Number of nodes to skip for pagination",
        ge=0,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable",
    )


class CallStackInput(BaseModel):
    """Input model for call stack tracing operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    node_name: str = Field(
        ...,
        description="Name of the function or class to trace (e.g., 'parse_file', 'IndexerDB')",
        min_length=1,
    )
    file_path: str | None = Field(
        default=None,
        description="Optional file path to disambiguate if multiple nodes have the same name",
    )
    direction: TraceDirection = Field(
        default=TraceDirection.BOTH,
        description="Trace direction: 'up' (callers), 'down' (callees), or 'both'",
    )
    depth: int = Field(
        default=1,
        description="Maximum traversal depth (how many levels to trace)",
        ge=1,
        le=10,
    )


class ImpactAnalysisInput(BaseModel):
    """Input model for impact analysis operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_path: str = Field(
        ...,
        description="Path to the file to analyze for impact (e.g., 'src/db.py')",
        min_length=1,
    )


class ReindexInput(BaseModel):
    """Input model for reindexing operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    path: str = Field(
        default=".",
        description="Path to index - file, directory, or '.' for project root",
    )


class ReferencesInput(BaseModel):
    """Input model for finding reference operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    symbol_name: str = Field(
        ...,
        description="Name of the function/class/variable to find references for",
        min_length=1,
    )


class DependenciesInput(BaseModel):
    """Input model for dependency analysis operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    file_path: str = Field(
        ...,
        description="Path to the file to check for outgoing dependencies",
        min_length=1,
    )


class SearchInput(BaseModel):
    """Input model for signature search operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    pattern: str = Field(
        ...,
        description=(
            "SQL pattern to search for in node signatures (e.g. '%List[str]%', 'async def%')"
        ),
        min_length=1,
    )


# =============================================================================
# Helper Classes
# =============================================================================


class GraphTraverser:
    """Traverses the call graph and builds output."""

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
        """Recursively traverse the graph."""
        if depth > max_depth:
            return

        # Check for cycles
        if current_id in self.visited:
            msg = _safe_str("🔄 [CYCLE DETECTED - circular dependency]")
            self.output.append(f"{'  ' * indent}{msg}")
            return

        self.visited.add(current_id)

        if direction == "up":
            query = """
                SELECT e.from_node_id as neighbor_id, e.relation_type, n.name, n.file_path 
                FROM edges e
                JOIN nodes n ON e.from_node_id = n.id
                WHERE e.to_node_id = ?
            """
            prefix = _safe_str("← called by")
        else:
            query = """
                SELECT e.to_node_id as neighbor_id, e.relation_type, n.name, n.file_path 
                FROM edges e
                JOIN nodes n ON e.to_node_id = n.id
                WHERE e.from_node_id = ?
            """
            prefix = _safe_str("→ calls")

        cursor = conn.execute(query, (current_id,))
        neighbors = cursor.fetchall()

        for n in neighbors:
            line = (
                f"{'  ' * indent}- {prefix} `{n['name']}` ({n['relation_type']}) "
                f"in `{n['file_path']}`"
            )
            self.output.append(line)
            self.traverse(n["neighbor_id"], depth + 1, max_depth, direction, indent + 1, conn)


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool(
    name="vibegraph_get_structural_summary",
    annotations={
        "title": "Get File Structure Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },  # type: ignore
)
async def vibegraph_get_structural_summary(params: StructuralSummaryInput) -> str:
    """
    Get a concise structural summary of a file (classes, functions, methods).

    This tool analyzes an indexed file and returns its structure, showing all
    classes, functions, and methods with their locations and signatures.

    Args:
        params (StructuralSummaryInput): Validated input parameters containing:
            - file_path (str): Path to the file to analyze (e.g., "src/parser.py")
            - limit (int): Maximum nodes to return, 1-500 (default: 100)
            - offset (int): Nodes to skip for pagination (default: 0)
            - response_format (str): "markdown" or "json" (default: "markdown")

    Returns:
        str: Formatted response containing:

        Markdown format:
        ```
        Structure for /path/to/file.py (showing 1-100 of 150 nodes):

        - [class] MyClass (L10-50)
        - [function] my_function(arg1, arg2) (L55-70)
        ...
        ... 50 more nodes available (use offset=100 to see more)
        ```

        JSON format:
        ```json
        {
            "file_path": "/path/to/file.py",
            "total": 150,
            "count": 100,
            "offset": 0,
            "has_more": true,
            "next_offset": 100,
            "nodes": [...]
        }
        ```

    Examples:
        - "Show me the structure of parser.py" -> file_path="src/parser.py"
        - "List all classes in db.py as JSON" -> file_path="src/db.py", response_format="json"

    Error Handling:
        - Returns "File might not be indexed" if file not found in database
        - Use vibegraph_reindex_project to index files first
    """
    try:
        db, root = _get_context_for_path(params.file_path)
        normalized_path = _normalize_path(params.file_path, root)

        with db._get_conn() as conn:
            # Get total count
            count_cursor = conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE file_path = ?", (normalized_path,)
            )
            total = count_cursor.fetchone()[0]

            # Get paginated results
            cursor = conn.execute(
                """SELECT id, name, kind, signature, start_line, end_line 
                   FROM nodes 
                   WHERE file_path = ? 
                   ORDER BY start_line
                   LIMIT ? OFFSET ?""",
                (normalized_path, params.limit, params.offset),
            )
            rows = cursor.fetchall()

        if total == 0:
            return (
                f"No structure found for {params.file_path}. "
                "File might not be indexed. Try vibegraph_reindex_project first."
            )

        # JSON format
        if params.response_format == ResponseFormat.JSON:
            import json

            nodes = [
                {
                    "name": row["name"],
                    "kind": row["kind"],
                    "signature": row["signature"],
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                }
                for row in rows
            ]
            response = {
                "file_path": normalized_path,
                "total": total,
                "count": len(nodes),
                "offset": params.offset,
                "has_more": total > params.offset + len(nodes),
                "next_offset": (
                    params.offset + len(nodes) if total > params.offset + len(nodes) else None
                ),
                "nodes": nodes,
            }
            return json.dumps(response, indent=2)

        # Markdown format (default)
        end_idx = min(params.offset + len(rows), total)
        summary = [
            f"Structure for `{normalized_path}` (showing {params.offset + 1}-{end_idx} "
            f"of {total} nodes):\n"
        ]

        for row in rows:
            info = f"- [{row['kind']}] **{row['name']}**"
            if row["signature"]:
                info += f"`{row['signature']}`"
            info += f" (L{row['start_line']}-{row['end_line']})"
            summary.append(info)

        if end_idx < total:
            remaining = total - end_idx
            next_offset = params.offset + params.limit
            summary.append(
                f"\n... {remaining} more nodes available (use offset={next_offset} to see more)"
            )

        return "\n".join(summary)

    except Exception as e:
        return _handle_error(e, f"analyzing {params.file_path}")


@mcp.tool(
    name="vibegraph_get_call_stack",
    annotations={
        "title": "Trace Call Stack",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },  # type: ignore
)
async def vibegraph_get_call_stack(params: CallStackInput) -> str:
    """
    Trace function calls up (callers) or down (callees).

    This tool traces the call graph from a given function or class, showing
    what calls it (callers/up) and what it calls (callees/down).

    Args:
        params (CallStackInput): Validated input parameters containing:
            - node_name (str): Name of the function/class (e.g., "parse_file")
            - file_path (str|None): Optional path to disambiguate (e.g., "src/parser.py")
            - direction (str): "up", "down", or "both" (default: "both")
            - depth (int): Max traversal depth 1-10 (default: 1)

    Returns:
        str: Markdown-formatted call graph showing:
            - Function/class name and location
            - Incoming callers (if direction includes "up")
            - Outgoing callees (if direction includes "down")
            - 🔄 [CYCLE DETECTED] if circular dependencies found

    Examples:
        - "What calls my function?" -> direction="up"
        - "What does this function call?" -> direction="down"
        - "Show full call tree for parse_file" -> node_name="parse_file", direction="both", depth=3

    Error Handling:
        - Returns "Node not found" if function/class doesn't exist in index
    """
    try:
        db, root = _get_context_for_path(params.file_path)

        with db._get_conn() as conn:
            query = "SELECT id, name, file_path, kind FROM nodes WHERE name = ?"
            query_params: list = [params.node_name]

            if params.file_path:
                query += " AND file_path = ?"
                query_params.append(_normalize_path(params.file_path, root))

            cursor = conn.execute(query, tuple(query_params))
            start_nodes = cursor.fetchall()

            if not start_nodes:
                return f"Node '{params.node_name}' not found. Is the file indexed?"

            traverser = GraphTraverser(db)

            for start_node in start_nodes:
                traverser.output.append(
                    f"### Trace for `{start_node['name']}` ({start_node['kind']}) "
                    f"in `{start_node['file_path']}`"
                )

                if params.direction in (TraceDirection.UP, TraceDirection.BOTH):
                    traverser.output.append("\n**Callers (Incoming):**")
                    traverser.traverse(start_node["id"], 1, params.depth, "up", 0, conn)
                    if not any(_safe_str("←") in line for line in traverser.output[-5:]):
                        traverser.output.append("  (no callers found)")
                    traverser.visited.clear()

                if params.direction in (TraceDirection.DOWN, TraceDirection.BOTH):
                    traverser.output.append("\n**Callees (Outgoing):**")
                    traverser.traverse(start_node["id"], 1, params.depth, "down", 0, conn)
                    if not any(_safe_str("→") in line for line in traverser.output[-5:]):
                        traverser.output.append("  (no callees found)")

        return "\n".join(traverser.output)

    except Exception as e:
        return _handle_error(e, f"tracing {params.node_name}")


@mcp.tool(
    name="vibegraph_impact_analysis",
    annotations={
        "title": "Analyze Change Impact",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },  # type: ignore
)
async def vibegraph_impact_analysis(params: ImpactAnalysisInput) -> str:
    """
    Analyze what other files/functions break if this file is modified.

    This tool identifies all external dependencies on a given file, helping
    you understand the blast radius of potential changes.

    Args:
        params (ImpactAnalysisInput): Validated input parameters containing:
            - file_path (str): Path to the file to analyze (e.g., "src/db.py")

    Returns:
        str: Markdown-formatted impact report showing:
            - List of functions/classes defined in the file
            - For each, what external code depends on it
            - Total impact count

    Examples:
        - "What breaks if I change db.py?" -> file_path="src/db.py"
        - "Impact analysis for parser module" -> file_path="src/parser.py"

    Limitations:
        - Currently shows only direct dependencies (1 level)
        - Transitive dependencies are planned for future versions

    Error Handling:
        - Returns "No nodes found" if file not indexed
    """
    try:
        db, root = _get_context_for_path(params.file_path)
        normalized_path = _normalize_path(params.file_path, root)

        with db._get_conn() as conn:
            cursor = conn.execute(
                "SELECT id, name FROM nodes WHERE file_path = ?", (normalized_path,)
            )
            file_nodes = cursor.fetchall()

            if not file_nodes:
                return f"No nodes found in {params.file_path}. Is it indexed?"

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
                msg = _safe_str("✅ No external dependencies found. Safe to refactor internally.")
                output.append(msg)
            else:
                output.append(f"\n**Total Impact**: {total_impact} dependent components")

        return "\n".join(output)

    except Exception as e:
        return _handle_error(e, f"analyzing impact for {params.file_path}")


@mcp.tool(
    name="vibegraph_find_references",
    annotations={
        "title": "Find Symbol References",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },  # type: ignore
)
async def vibegraph_find_references(params: ReferencesInput) -> str:
    """
    Find where a specific function or class is called/used.

    Queries the graph for 'calls' or 'references' edges pointing TO the given symbol name.

    Args:
        params (ReferencesInput): Validated input parameters containing:
            - symbol_name (str): The name to search for (e.g. "IndexerDB")

    Returns:
        str: Markdown list of usages with location info.
    """
    try:
        # Since we don't have a path, we fall back to CWD to find the root
        db, _ = _get_context_for_path(".")
        with db._get_conn() as conn:
            # First find potential target node IDs by name
            # (There might be multiple if same name used in diff files)
            cursor = conn.execute(
                "SELECT id, name, file_path FROM nodes WHERE name = ?", (params.symbol_name,)
            )
            targets = cursor.fetchall()

            if not targets:
                return f"Symbol '{params.symbol_name}' not found in index."

            output = [f"## References to `{params.symbol_name}`"]

            for target in targets:
                target_desc = f"`{target['name']}` from `{target['file_path']}`"

                # Query incoming edges of type 'calls' or 'references'
                query = """
                    SELECT n.name, n.file_path, n.start_line, e.relation_type
                    FROM edges e
                    JOIN nodes n ON e.from_node_id = n.id
                    WHERE e.to_node_id = ? AND e.relation_type IN ('calls', 'references')
                """
                cursor = conn.execute(query, (target["id"],))
                refs = cursor.fetchall()

                if refs:
                    output.append(f"\n### Usages of {target_desc}")
                    for ref in refs:
                        output.append(
                            f"- Used by `{ref['name']}` in `{ref['file_path']}` "
                            f"(L{ref['start_line']}) [{ref['relation_type']}]"
                        )
                else:
                    output.append(f"\n### Usages of {target_desc}\n- No direct calls found.")

        return "\n".join(output)
    except Exception as e:
        return _handle_error(e, f"finding references for {params.symbol_name}")


@mcp.tool(
    name="vibegraph_get_dependencies",
    annotations={
        "title": "Get File Dependencies",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },  # type: ignore
)
async def vibegraph_get_dependencies(params: DependenciesInput) -> str:
    """
    List modules and symbols imported by a specific file.

    Queries outgoing 'imports' edges from the file.

    Args:
        params (DependenciesInput): Validated input parameters containing:
            - file_path (str): Path to the file.

    Returns:
        str: Markdown list of dependencies.
    """
    try:
        db, root = _get_context_for_path(params.file_path)
        normalized_path = _normalize_path(params.file_path, root)

        with db._get_conn() as conn:
            # Find nodes in this file, then check their outgoing import edges?
            # Actually import edges usually link from a file-scope/module node OR
            # generic nodes in that file.

            # Let's query outgoing edges from ANY node in this file having relation 'imports'
            query = """
                SELECT DISTINCT n_to.name, n_to.file_path, n_to.kind
                FROM nodes n_from
                JOIN edges e ON n_from.id = e.from_node_id
                JOIN nodes n_to ON e.to_node_id = n_to.id
                WHERE n_from.file_path = ? AND e.relation_type = 'imports'
             """

            cursor = conn.execute(query, (normalized_path,))
            deps = cursor.fetchall()

            output = [f"## Dependencies for `{normalized_path}`"]
            if not deps:
                output.append("No explicit imports found in index.")
            else:
                for dep in deps:
                    output.append(
                        f"- Imports `{dep['name']}` ({dep['kind']}) from `{dep['file_path']}`"
                    )

        return "\n".join(output)
    except Exception as e:
        return _handle_error(e, f"getting dependencies for {params.file_path}")


@mcp.tool(
    name="vibegraph_search_by_signature",
    annotations={
        "title": "Search by Signature",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },  # type: ignore
)
async def vibegraph_search_by_signature(params: SearchInput) -> str:
    """
    Search for functions matching a specific signature pattern.

    Useful for finding functions with specific arguments or return types.

    Args:
        params (SearchInput): Patern using SQL LIKE syntax (e.g. "%List[str]%")

    Returns:
        str: List of matching functions.
    """
    try:
        db, _ = _get_context_for_path(".")
        with db._get_conn() as conn:
            query = (
                "SELECT name, signature, file_path, start_line "
                "FROM nodes WHERE signature LIKE ? LIMIT 50"
            )
            cursor = conn.execute(query, (params.pattern,))
            rows = cursor.fetchall()

            output = [f"## Signature Search: `{params.pattern}`"]
            if not rows:
                output.append("No matches found.")
            else:
                for row in rows:
                    output.append(
                        f"- **`{row['name']}`**: `{row['signature']}`\n"
                        f"  - In `{row['file_path']}`:L{row['start_line']}"
                    )

        return "\n".join(output)
    except Exception as e:
        return _handle_error(e, f"searching signature {params.pattern}")


@mcp.tool(
    name="vibegraph_reindex_project",
    annotations={
        "title": "Reindex Project Files",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },  # type: ignore
)
async def vibegraph_reindex_project(params: ReindexInput) -> str:
    """
    Reindex a file or directory recursively.

    This tool scans and indexes source code files, extracting structural
    information (classes, functions, calls) into the database. Uses
    .gitignore for filtering.

    Args:
        params (ReindexInput): Validated input parameters containing:
            - path (str): Path to index - file, directory, or "." for project root

    Returns:
        str: Success message with path indexed, or error message

    Examples:
        - "Index the current project" -> path="."
        - "Reindex just the src folder" -> path="src"
        - "Index a specific file" -> path="src/parser.py"

    Features:
        - Respects .gitignore patterns
        - Skips common noise directories (node_modules, __pycache__, .venv)
        - Currently supports Python files (.py)

    Error Handling:
        - Returns error message if path doesn't exist
        - Continues on individual file errors, reports overall success
    """
    try:
        db, _ = _get_context_for_path(params.path)
        target_path = Path(params.path).resolve()

        with redirect_stdout(sys.stderr):
            reindex_all(db, str(target_path), verbose=True)
        return _safe_str(f"✅ Successfully reindexed: {target_path}")
    except Exception as e:
        return _handle_error(e, f"reindexing {params.path}")


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Entry point for the vibegraph-mcp console script."""
    mcp.run()


if __name__ == "__main__":
    main()
