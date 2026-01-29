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
import { RefreshCw, Search, Layers, Activity, Code, Filter } from 'lucide-react';
import dagre from 'dagre';
import './App.css';

// API Configuration
const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

// Graph Layout Helper
const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const NODE_WIDTH = 250;
const NODE_HEIGHT = 150;

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    // Center the node
    node.position = {
      x: nodeWithPosition.x - NODE_WIDTH / 2,
      y: nodeWithPosition.y - NODE_HEIGHT / 2,
    };
    return node;
  });

  return { nodes: layoutedNodes, edges };
};

// Custom Node Component
const VibeNode = memo(({ data }: { data: any }) => {
  const isClass = data.kind === 'class';
  const isInterface = data.kind === 'interface';
  const isHighlighted = data.isHighlighted;
  const isDimmed = data.isDimmed;

  let borderColor = '#6366f1';
  let bgColor = '#1a1b23';

  if (isClass) borderColor = '#a855f7';
  if (isInterface) borderColor = '#10b981';

  // highlight styles
  if (isHighlighted) {
    bgColor = '#2e2f3d'; // slightly lighter background
    borderColor = '#ffffff'; // bright border
  }

  const style: React.CSSProperties = {
    borderLeftColor: borderColor,
    backgroundColor: bgColor,
    opacity: isDimmed ? 0.2 : 1,
    transition: 'all 0.3s ease',
    border: isHighlighted ? `2px solid ${borderColor}` : undefined,
    borderLeft: isHighlighted ? `2px solid ${borderColor}` : `3px solid ${borderColor}`
  };

  return (
    <div className="vibe-node" style={style}>
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
  const [error, setError] = useState<string | null>(null);

  // Interaction State
  const [filter, setFilter] = useState('');
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set(['function', 'class', 'interface', 'module']));
  const [lastUpdate, setLastUpdate] = useState<string>('');

  // Ref for raw graph data to support client-side filtering
  const rawData = useRef<{ nodes: any[], edges: any[] }>({ nodes: [], edges: [] });
  const ws = useRef<WebSocket | null>(null);

  // Layout Graph w/ Filters
  const applyLayoutAndFilters = useCallback(() => {
    const { nodes: rawNodes, edges: rawEdges } = rawData.current;

    if (rawNodes.length === 0) {
      console.warn("No nodes in raw data");
      return;
    }

    // 1. Filter Nodes by Type
    let filteredNodes = rawNodes.filter(n => activeFilters.has(n.kind));

    // 2. Filter Edges (must connect two visible nodes)
    const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
    let filteredEdges = rawEdges.filter(e =>
      visibleNodeIds.has(e.from_node_id) && visibleNodeIds.has(e.to_node_id)
    );

    // 3. Search / Highlight Logic
    // If filter text exists, mark nodes as highlighted or dimmed
    const searchTerm = filter.toLowerCase();
    const searchActive = searchTerm.length > 0;

    const flowNodes: Node[] = filteredNodes.map((n) => {
      const matches = searchActive && (n.name.toLowerCase().includes(searchTerm) || n.file_path.toLowerCase().includes(searchTerm));

      return {
        id: n.id,
        type: 'vibeNode',
        position: { x: 0, y: 0 }, // Initial pos, will be set by dagre
        data: {
          label: n.name,
          kind: n.kind,
          signature: n.signature,
          docstring: n.docstring,
          isHighlighted: matches,
          isDimmed: searchActive && !matches
        },
      };
    });

    const flowEdges: Edge[] = filteredEdges.map((e) => ({
      id: `${e.from_node_id}-${e.to_node_id}-${e.relation_type}`,
      source: e.from_node_id,
      target: e.to_node_id,
      label: e.relation_type,
      type: 'smoothstep', // Better for hierarchical
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: 'rgba(255, 255, 255, 0.3)'
      },
      animated: true,
      style: {
        stroke: 'rgba(255, 255, 255, 0.2)',
        opacity: searchActive ? 0.1 : 1
      }
    }));

    // 4. Apply Dagre Layout
    try {
      const { nodes: layoutNodes, edges: layoutEdges } = getLayoutedElements(
        flowNodes,
        flowEdges
      );

      setNodes(layoutNodes);
      setEdges(layoutEdges);
    } catch (layoutError) {
      console.error("Layout Error:", layoutError);
      setError("Layout failed (Dagre error). Check console.");
    }
  }, [activeFilters, filter, setNodes, setEdges]);


  const fetchGraph = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log(`Fetching graph from ${API_URL}/graph...`);
      const res = await axios.get(`${API_URL}/graph`);
      console.log("Graph data received:", res.data);

      if (!res.data || !res.data.nodes) {
        setError("Invalid data format received from API");
        return;
      }

      rawData.current = res.data;
      setLastUpdate(new Date().toLocaleTimeString());

      if (res.data.nodes.length === 0) {
        setError("Database is empty. Did you run the indexer?");
      } else {
        applyLayoutAndFilters();
      }
    } catch (err: any) {
      console.error("Failed to fetch graph", err);
      setError(err.message || "Failed to fetch graph");
    } finally {
      setLoading(false);
    }
  };

  // Re-run layout when filters change
  useEffect(() => {
    applyLayoutAndFilters();
  }, [applyLayoutAndFilters]);

  // Initial Load & WS
  useEffect(() => {
    fetchGraph();

    const connectWS = () => {
      ws.current = new WebSocket(WS_URL);
      ws.current.onopen = () => console.log("Vibe-Sync Active");
      ws.current.onmessage = (event) => {
        if (event.data === "refresh") {
          // Re-fetch everything on update
          fetchGraph();
        }
      };
      ws.current.onclose = () => {
        console.log("WS Disconnected, retrying...");
        setTimeout(connectWS, 3000);
      };
    };

    connectWS();
    return () => { ws.current?.close(); };
  }, []);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  const toggleFilter = (kind: string) => {
    const newFilters = new Set(activeFilters);
    if (newFilters.has(kind)) {
      newFilters.delete(kind);
    } else {
      newFilters.add(kind);
    }
    setActiveFilters(newFilters);
  };

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
            placeholder="Search symbols..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>

        <button className="vibe-button" onClick={() => fetchGraph()} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          {loading ? 'Syncing...' : 'Sync Graph'}
        </button>

        <div className="stats-panel">
          <Layers size={14} /> <span>{nodes.length > 0 ? nodes.length : (rawData.current?.nodes?.length || 0)} Nodes</span>
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

        {/* Loading Overlay */}
        {loading && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            background: 'rgba(26, 27, 35, 0.8)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 20,
            backdropFilter: 'blur(4px)',
            color: '#fff'
          }}>
            <RefreshCw size={48} className="spin" style={{ color: '#6366f1', marginBottom: 16 }} />
            <div style={{ fontSize: '18px', fontWeight: 600 }}>Syncing VibeGraph...</div>
            <div style={{ fontSize: '14px', opacity: 0.6, marginTop: 4 }}>Parsing AST & building relationships</div>
          </div>
        )}

        {/* Error Overlay */}
        {error && (
          <div style={{
            position: 'absolute',
            top: 20,
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'rgba(239, 68, 68, 0.9)',
            color: 'white',
            padding: '12px 24px',
            borderRadius: '8px',
            zIndex: 30,
            backdropFilter: 'blur(4px)',
            border: '1px solid rgba(255,255,255,0.2)',
            display: 'flex',
            alignItems: 'center',
            gap: 12
          }}>
            <div style={{ fontWeight: 600 }}>Error:</div>
            <div>{error}</div>
            <button
              onClick={() => fetchGraph()}
              style={{
                background: 'rgba(255,255,255,0.2)',
                border: 'none',
                borderRadius: 4,
                padding: '4px 8px',
                color: 'white',
                cursor: 'pointer',
                marginLeft: 12
              }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Filter Panel */}
        <Panel position="top-right" className="glass-panel" style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: 8, marginTop: '80px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Filter size={12} /> Filters
          </div>
          {['function', 'class', 'interface', 'module'].map(kind => (
            <label key={kind} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '12px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={activeFilters.has(kind)}
                onChange={() => toggleFilter(kind)}
              />
              <span style={{ textTransform: 'capitalize' }}>{kind}</span>
            </label>
          ))}
        </Panel>

        {/* Legend */}
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
