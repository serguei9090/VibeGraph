from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from typing import List
from vibegraph.indexer.db import IndexerDB
from vibegraph.indexer.watcher import start_observer

# Global Managers
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()
db = IndexerDB()

# Lifespan for Watcher
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Callback to trigger WS broadcast
    # We need to run the async broadcast from the sync watchdog callback
    loop = asyncio.get_running_loop()
    
    def on_change():
        # Schedule the broadcast coroutine in the event loop
        asyncio.run_coroutine_threadsafe(manager.broadcast("refresh"), loop)

    # Start watching current directory (or passed arg)
    # Ideally should be configurable. For now, "." (root of project)
    observer = start_observer(".", db, on_change)
    yield
    observer.stop()
    observer.join()

app = FastAPI(title="VibeGraph API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/graph")
def get_graph(file_path: str = None):
    """
    Return nodes and edges.
    If file_path is provided, filter nodes by that file (plus connected edges).
    """
    with db._get_conn() as conn:
        if file_path:
            # Get nodes in file
            nodes_cursor = conn.execute("SELECT * FROM nodes WHERE file_path = ?", (file_path,))
        else:
            # Get all nodes
            nodes_cursor = conn.execute("SELECT * FROM nodes")
            
        nodes = [dict(row) for row in nodes_cursor.fetchall()]
        
        # Determine edges to return
        if not nodes:
             return {"nodes": [], "edges": []}

        if file_path:
            # Only return edges connected to these nodes (simple) or all edges?
            # Let's return all edges for now to be safe, or filter:
            # Since edges table uses IDs, and we have node IDs...
            node_ids = tuple(n['id'] for n in nodes)
            if node_ids:
                placeholders = ",".join("?" for _ in node_ids)
                # Edges causing these nodes (incoming) OR caused by these nodes (outgoing)
                query = f"SELECT * FROM edges WHERE from_node_id IN ({placeholders}) OR to_node_id IN ({placeholders})"
                edges_cursor = conn.execute(query, node_ids + node_ids)
                edges = [dict(row) for row in edges_cursor.fetchall()]
            else:
                 edges = []
        else:
            edges_cursor = conn.execute("SELECT * FROM edges")
            edges = [dict(row) for row in edges_cursor.fetchall()]
        
    return {
        "nodes": nodes,
        "edges": edges
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
