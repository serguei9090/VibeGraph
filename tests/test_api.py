from fastapi.testclient import TestClient
from vibegraph.server_api import app
from vibegraph.indexer.db import IndexerDB, Node
import pytest
import os

client = TestClient(app)

@pytest.fixture
def mock_db(monkeypatch, tmp_path):
    """Overrides the global db in server_api.py to use a temp file DB."""
    db_file = tmp_path / "test_api_vibegraph.db"
    db = IndexerDB(str(db_file))
    
    # Add Sample Data
    db.upsert_node(Node(id="a", name="NodeA", kind="class", file_path="a.py", start_line=1, end_line=10))
    
    # Monkeypatch the 'db' variable in server_api
    import vibegraph.server_api
    monkeypatch.setattr(vibegraph.server_api, "db", db)
    return db

def test_get_graph(mock_db):
    response = client.get("/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data['nodes']) == 1
    assert data['nodes'][0]['name'] == "NodeA"

def test_get_graph_filtered(mock_db):
    response = client.get("/graph?file_path=a.py")
    assert response.status_code == 200
    data = response.json()
    assert len(data['nodes']) == 1
    
    response_empty = client.get("/graph?file_path=missing.py")
    assert len(response_empty.json()['nodes']) == 0
