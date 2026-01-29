"""
Tests for VibeGraph MCP Server.

Tests the refactored MCP tools with Pydantic input models and async functions.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from vibegraph.indexer.db import Edge, IndexerDB, Node
from vibegraph.mcp.server import (
    CallStackInput,
    ImpactAnalysisInput,
    ResponseFormat,
    StructuralSummaryInput,
    TraceDirection,
    vibegraph_get_call_stack,
    vibegraph_get_structural_summary,
    vibegraph_impact_analysis,
)


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


# =============================================================================
# Tests for vibegraph_get_structural_summary
# =============================================================================


@pytest.mark.asyncio
async def test_get_structural_summary(mock_db):
    """Test structural summary returns correct info."""
    params = StructuralSummaryInput(file_path="a.py")
    summary = await vibegraph_get_structural_summary(params)

    # After path normalization, output contains absolute path
    assert "[function] **func_a**`(x)` (L1-5)" in summary


@pytest.mark.asyncio
async def test_get_structural_summary_json(mock_db):
    """Test structural summary JSON output."""
    params = StructuralSummaryInput(
        file_path="a.py",
        response_format=ResponseFormat.JSON,
    )
    summary = await vibegraph_get_structural_summary(params)

    # Should be valid JSON with expected fields
    import json

    data = json.loads(summary)
    assert data["total"] == 1
    assert data["nodes"][0]["name"] == "func_a"
    assert data["nodes"][0]["kind"] == "function"


@pytest.mark.asyncio
async def test_get_structural_summary_not_found(mock_db):
    """Test structural summary for non-indexed file."""
    params = StructuralSummaryInput(file_path="nonexistent.py")
    summary = await vibegraph_get_structural_summary(params)

    assert "not be indexed" in summary


# =============================================================================
# Tests for vibegraph_get_call_stack
# =============================================================================


@pytest.mark.asyncio
async def test_get_call_stack_up(mock_db):
    """Trace callers of func_a (should be func_b)."""
    params = CallStackInput(node_name="func_a", direction=TraceDirection.UP)
    trace = await vibegraph_get_call_stack(params)

    assert "Trace for `func_a`" in trace
    assert "Callers (Incoming):" in trace
    assert "← called by `func_b` (calls)" in trace


@pytest.mark.asyncio
async def test_get_call_stack_down(mock_db):
    """Trace callees of func_b (should be func_a)."""
    params = CallStackInput(node_name="func_b", direction=TraceDirection.DOWN)
    trace = await vibegraph_get_call_stack(params)

    assert "Trace for `func_b`" in trace
    assert "Callees (Outgoing):" in trace
    assert "→ calls `func_a` (calls)" in trace


@pytest.mark.asyncio
async def test_get_call_stack_not_found(mock_db):
    """Test call stack for non-existent node."""
    params = CallStackInput(node_name="nonexistent_func")
    trace = await vibegraph_get_call_stack(params)

    assert "not found" in trace


@pytest.mark.asyncio
async def test_get_call_stack_both(mock_db):
    """Test call stack with both directions."""
    params = CallStackInput(node_name="func_a", direction=TraceDirection.BOTH)
    trace = await vibegraph_get_call_stack(params)

    assert "Callers (Incoming):" in trace
    assert "Callees (Outgoing):" in trace


# =============================================================================
# Tests for vibegraph_impact_analysis
# =============================================================================


@pytest.mark.asyncio
async def test_impact_analysis(mock_db):
    """If we change a.py (func_a), b.py (func_b) should be affected."""
    params = ImpactAnalysisInput(file_path="a.py")
    impact = await vibegraph_impact_analysis(params)

    assert "Impact Analysis" in impact
    assert "**`func_a`** is used by:" in impact
    assert "`func_b`" in impact


@pytest.mark.asyncio
async def test_impact_analysis_no_impact(mock_db):
    """If we change b.py, nothing depends on it."""
    params = ImpactAnalysisInput(file_path="b.py")
    impact = await vibegraph_impact_analysis(params)

    assert "Impact Analysis" in impact
    assert "No external dependencies found" in impact


# =============================================================================
# Tests for Pydantic Validation
# =============================================================================


def test_structural_summary_input_validation():
    """Test input validation for structural summary."""
    # Valid input
    params = StructuralSummaryInput(file_path="test.py", limit=50, offset=10)
    assert params.file_path == "test.py"
    assert params.limit == 50
    assert params.offset == 10

    # Invalid limit (too high)
    with pytest.raises(ValidationError):
        StructuralSummaryInput(file_path="test.py", limit=1000)

    # Invalid offset (negative)
    with pytest.raises(ValidationError):
        StructuralSummaryInput(file_path="test.py", offset=-1)


def test_call_stack_input_validation():
    """Test input validation for call stack."""
    # Valid input
    params = CallStackInput(node_name="my_func", depth=5)
    assert params.node_name == "my_func"
    assert params.depth == 5

    # Invalid depth (too high)
    with pytest.raises(ValidationError):
        CallStackInput(node_name="my_func", depth=20)

    # Empty node name
    with pytest.raises(ValidationError):
        CallStackInput(node_name="")
