from pathlib import Path

import pytest

from vibegraph.indexer.db import Edge, IndexerDB, Node
from vibegraph.mcp.server import get_call_stack, get_structural_summary, impact_analysis


# Mock Database Setup
@pytest.fixture
def mock_db(monkeypatch, tmp_path):
    """Overrides the _get_db function in server.py to use a temp file DB."""

    # Create a temp DB file
    db_file = tmp_path / "test_vibegraph.db"
    db = IndexerDB(str(db_file))

    # Use absolute paths to match path normalization behavior
    a_py_path = str(Path("a.py").resolve())
    b_py_path = str(Path("b.py").resolve())

    # Add Nodes
    # File A: Defines func_a
    db.upsert_node(
        Node(
            id="a",
            name="func_a",
            kind="function",
            file_path=a_py_path,
            start_line=1,
            end_line=5,
            signature="(x)",
            docstring="Doc A",
        )
    )
    # File B: Defines func_b, calls func_a
    db.upsert_node(
        Node(
            id="b",
            name="func_b",
            kind="function",
            file_path=b_py_path,
            start_line=1,
            end_line=5,
            signature="()",
            docstring="Doc B",
        )
    )

    # Add Edges
    # func_b calls func_a
    db.upsert_edge(Edge(from_node_id="b", to_node_id="a", relation_type="calls"))

    # Monkeypatch
    import vibegraph.mcp.server

    monkeypatch.setattr(vibegraph.mcp.server, "_get_db", lambda: db)

    return db


def test_get_structural_summary(mock_db):
    summary = get_structural_summary("a.py")
    # After path normalization, output contains absolute path
    assert "[function] func_a(x) (L1-5)" in summary


def test_get_call_stack_up(mock_db):
    # Trace callers of func_a (should be func_b)
    trace = get_call_stack("func_a", direction="up")
    assert "Trace for `func_a`" in trace
    assert "Callers (Incoming):" in trace
    assert "← called by `func_b` (calls)" in trace


def test_get_call_stack_down(mock_db):
    # Trace callees of func_b (should be func_a)
    trace = get_call_stack("func_b", direction="down")
    assert "Trace for `func_b`" in trace
    assert "Callees (Outgoing):" in trace
    assert "→ calls `func_a` (calls)" in trace


def test_impact_analysis(mock_db):
    # If we change a.py (func_a), b.py (func_b) should be affected
    impact = impact_analysis("a.py")
    assert "Impact Analysis" in impact
    assert "**`func_a`** is used by:" in impact
    assert "`func_b`" in impact


def test_impact_analysis_no_impact(mock_db):
    # If we change b.py, nothing depends on it
    impact = impact_analysis("b.py")
    assert "Impact Analysis" in impact
    assert "No external dependencies found" in impact
