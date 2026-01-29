import { useState, useCallback, useEffect, useRef, memo } from 'react';
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
  Handle,
  Position,
  Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import axios from 'axios';
import { RefreshCw, Search, Layers, Activity, Code } from 'lucide-react';
import './App.css';

// API Configuration
const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

// Custom Node Component
const VibeNode = memo(({ data }: { data: any }) => {
  const isClass = data.kind === 'class';
  const isInterface = data.kind === 'interface';

  let borderColor = '#6366f1';
  if (isClass) borderColor = '#a855f7';
  if (isInterface) borderColor = '#10b981';

  return (
    <div className="vibe-node" style={{ borderLeftColor: borderColor }}>
      <Handle type="target" position={Position.Top} style={{ background: borderColor }} />
      <div className="node-type">{data.kind}</div>
      <div className="node-name">{data.label}</div>
      {data.signature && (
        <div style={{ marginTop: 4, fontSize: '9px', opacity: 0.6, fontFamily: 'JetBrains Mono' }}>
          {data.signature.length > 30 ? data.signature.substring(0, 30) + '...' : data.signature}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: borderColor }} />
    </div>
  );
});

const nodeTypes = {
  vibeNode: VibeNode,
};

const initialNodes: Node[] = [];
const initialEdges: Edge[] = [];

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('');
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const ws = useRef<WebSocket | null>(null);

  const fetchGraph = async (fileFilter?: string) => {
    setLoading(true);
    try {
      const url = fileFilter
        ? `${API_URL}/graph?file_path=${encodeURIComponent(fileFilter)}`
        : `${API_URL}/graph`;

      const res = await axios.get(url);
      const { nodes: apiNodes, edges: apiEdges } = res.data;

      // Layout logic (Simple circular or force-directed would be better, but grid is safe)
      const layoutNodes = apiNodes.map((n: any, index: number) => {
        const row = Math.floor(index / 8);
        const col = index % 8;
        return {
          id: n.id,
          type: 'vibeNode',
          position: { x: col * 250, y: row * 150 },
          data: {
            label: n.name,
            kind: n.kind,
            signature: n.signature,
            docstring: n.docstring
          },
        };
      });

      const layoutEdges = apiEdges.map((e: any) => ({
        id: `${e.from_node_id}-${e.to_node_id}-${e.relation_type}`,
        source: e.from_node_id,
        target: e.to_node_id,
        label: e.relation_type,
        type: 'smoothstep',
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: 'rgba(255, 255, 255, 0.3)'
        },
        animated: true,
        style: { stroke: 'rgba(255, 255, 255, 0.2)' }
      }));

      setNodes(layoutNodes);
      setEdges(layoutEdges);
      setLastUpdate(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("Failed to fetch graph", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();

    // WebSocket Setup
    const connectWS = () => {
      ws.current = new WebSocket(WS_URL);
      ws.current.onopen = () => console.log("Vibe-Sync Active");
      ws.current.onmessage = (event) => {
        if (event.data === "refresh") {
          fetchGraph(filter);
        }
      };
      ws.current.onclose = () => {
        console.log("WS Disconnected, retrying...");
        setTimeout(connectWS, 3000);
      };
    };

    connectWS();

    return () => {
      ws.current?.close();
    };
  }, []);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div className="graph-container">
      {/* Vibe-Bar Header */}
      <div className="vibe-header glass-panel">
        <Activity size={24} color="#6366f1" />
        <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, letterSpacing: '-0.02em' }}>
          VIBEGRAPH <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>MAP ROOM</span>
        </h2>

        <div style={{ position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: 10, color: 'var(--text-dim)' }} />
          <input
            className="vibe-input"
            type="text"
            placeholder="Search by file path..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchGraph(filter)}
          />
        </div>

        <button className="vibe-button" onClick={() => fetchGraph(filter)} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          {loading ? 'Syncing...' : 'Sync Graph'}
        </button>

        <div className="stats-panel">
          <Layers size={14} /> <span>{nodes.length} Nodes</span>
          <div style={{ width: 1, height: 16, background: 'var(--border-color)' }}></div>
          <Code size={14} /> <span>{edges.length} Edges</span>
          <div style={{ width: 1, height: 16, background: 'var(--border-color)' }}></div>
          <span style={{ fontSize: '11px', opacity: 0.5 }}>Last Sync: {lastUpdate}</span>
        </div>
      </div>

      {/* Main Graph Canvas */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
      >
        <Controls />
        <Background color="#1a1b23" gap={20} size={1} />

        <Panel position="bottom-right" className="glass-panel" style={{ padding: '8px 12px', marginBottom: 20, marginRight: 20 }}>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ display: 'inline-block', width: 8, height: 8, background: '#6366f1', borderRadius: 2 }}></span> Function
            <span style={{ display: 'inline-block', width: 8, height: 8, background: '#a855f7', borderRadius: 2 }}></span> Class
            <span style={{ display: 'inline-block', width: 8, height: 8, background: '#10b981', borderRadius: 2 }}></span> Interface
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}
