import json
import sqlite3
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel


class Node(BaseModel):
    id: str
    name: str
    kind: Literal[
        "function", "class", "module", "interface", "variable", "struct", "trait", "impl", "method"
    ]
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    signature: str | None = None
    docstring: str | None = None
    decorators: list[str] | None = None
    visibility: str | None = None


class Edge(BaseModel):
    from_node_id: str
    to_node_id: str
    relation_type: Literal[
        "calls", "defines", "inherits", "references", "imports", "implements", "returns"
    ]


class IndexerDB:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            # Try to find the project root relative to this file's location
            # This file is at: src/vibegraph/indexer/db.py
            # Project root is 3 levels up from db.py
            pkg_root = Path(__file__).resolve().parent.parent.parent.parent
            context_dir = pkg_root / "vibegraph_context"
            context_dir.mkdir(exist_ok=True)
            self.db_path = str(context_dir / "vibegraph.db")
        else:
            self.db_path = db_path

        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize the database schema if it doesn't exist."""
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found at {schema_path}")

        with self._get_conn() as conn:
            with open(schema_path) as f:
                conn.executescript(f.read())

    def upsert_node(self, node: Node) -> None:
        """Insert or replace a node."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO nodes (
                    id, name, kind, file_path, start_line, end_line, signature, docstring,
                    decorators, visibility
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    node.name,
                    node.kind,
                    node.file_path,
                    node.start_line,
                    node.end_line,
                    node.signature,
                    node.docstring,
                    json.dumps(node.decorators) if node.decorators else None,
                    node.visibility,
                ),
            )
            conn.commit()

    def upsert_edge(self, edge: Edge) -> None:
        """Insert an edge."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO edges (from_node_id, to_node_id, relation_type)
                VALUES (?, ?, ?)
                """,
                (edge.from_node_id, edge.to_node_id, edge.relation_type),
            )
            conn.commit()

    def clear_file(self, file_path: str) -> None:
        """Remove all nodes and edges associated with a file."""
        # Note: We need to be careful with edges.
        # Use simple logic for now: delete nodes defined in this file.
        # Edges originating from this file should be deleted.
        # Edges pointing to this file... ideally should remain if they are from other files,
        # but if we delete the node, the foreign key might cascade or be invalid.
        # For this phase, we usually just delete nodes from this file and edges FROM this file.
        # Edges TO this file are trickier if we don't have cascade delete.
        # Let's assume content-addressable or path-addressable IDs will be restored.

        # First, find IDs of nodes in this file
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id FROM nodes WHERE file_path = ?", (file_path,))
            node_ids = [row[0] for row in cursor.fetchall()]

            if not node_ids:
                return

            # Delete edges originating from these nodes
            placeholders = ",".join("?" for _ in node_ids)
            conn.execute(f"DELETE FROM edges WHERE from_node_id IN ({placeholders})", node_ids)

            # Delete the nodes themselves
            conn.execute("DELETE FROM nodes WHERE file_path = ?", (file_path,))
            conn.commit()

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
