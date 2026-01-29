import { useState, useCallback, useEffect, useRef } from 'react';
import ReactFlow, {
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import axios from 'axios';
import { RefreshCw, Search, Layers } from 'lucide-react';

// API Configuration
const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

const initialNodes: Node[] = [];
const initialEdges: Edge[] = [];

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('');
  const ws = useRef<WebSocket | null>(null);

  const fetchGraph = async (fileFilter?: string) => {
    setLoading(true);
    try {
      const url = fileFilter
        ? `${API_URL}/graph?file_path=${encodeURIComponent(fileFilter)}`
        : `${API_URL}/graph`;

      const res = await axios.get(url);
      const { nodes: apiNodes, edges: apiEdges } = res.data;

      // Layout logic (simple generic placement for now)
      // In a real app, use dagre or elkjs for auto-layout
      const layoutNodes = apiNodes.map((n: any, index: number) => ({
        id: n.id,
        position: { x: (index % 10) * 200, y: Math.floor(index / 10) * 100 },
        data: { label: `${n.name} (${n.kind})` },
        style: {
          border: '1px solid #777',
          padding: 10,
          borderRadius: 5,
          background: n.kind === 'function' ? '#e3f2fd' : '#f3e5f5'
        },
      }));

      const layoutEdges = apiEdges.map((e: any) => ({
        id: `${e.from_node_id}-${e.to_node_id}-${e.relation_type}`,
        source: e.from_node_id,
        target: e.to_node_id,
        label: e.relation_type,
        type: 'smoothstep',
        markerEnd: { type: MarkerType.ArrowClosed },
        animated: true,
      }));

      setNodes(layoutNodes);
      setEdges(layoutEdges);
    } catch (err) {
      console.error("Failed to fetch graph", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();

    // WebSocket Setup
    ws.current = new WebSocket(WS_URL);
    ws.current.onopen = () => console.log("WS Connected");
    ws.current.onmessage = (event) => {
      console.log("WS Message:", event.data);
      if (event.data === "refresh") {
        fetchGraph(filter);
      }
    };

    return () => {
      ws.current?.close();
    };
  }, []);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header / Vibe-Bar */}
      <div style={{ padding: '10px 20px', borderBottom: '1px solid #ddd', display: 'flex', gap: 10, alignItems: 'center', background: '#f9f9f9' }}>
        <h2 style={{ margin: 0, marginRight: 20 }}>VibeGraph Map Room</h2>

        <div style={{ position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: 8, top: 8, color: '#888' }} />
          <input
            type="text"
            placeholder="Filter by file path..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchGraph(filter)}
            style={{ padding: '5px 5px 5px 30px', borderRadius: 4, border: '1px solid #ccc' }}
          />
        </div>

        <button onClick={() => fetchGraph(filter)} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', cursor: 'pointer' }}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>

        <div style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#666' }}>
          <Layers size={14} style={{ verticalAlign: 'middle' }} /> {nodes.length} Nodes | {edges.length} Edges
        </div>
      </div>

      {/* Graph Area */}
      <div style={{ flex: 1 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          <Controls />
          <Background color="#aaa" gap={16} />
        </ReactFlow>
      </div>

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
