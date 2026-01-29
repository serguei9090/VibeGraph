# VibeGraph: The Nervous System MCP

> **Philosophy**: Structural Truth > Statistical Guessing

VibeGraph is a code intelligence system that treats your codebase as a **nervous system**. Instead of vector embeddings and similarity search, it uses Tree-sitter for AST parsing and SQLite for relational queries. The result? A structural graph that AI agents can query and you can visualize in real-time.

## Features

- **🧠 Structural Indexing**: Tree-sitter AST parsing (Python supported, extensible)
- **🔍 MCP Server**: AI-queryable tools (`get_call_stack`, `impact_analysis`, `get_structural_summary`)
- **🗺️ Map Room**: React Flow visualizer with live updates
- **⚡ Vibe-Sync**: Real-time WebSocket updates when code changes
- **🧪 Fully Tested**: Pytest suite for indexer, MCP tools, and API

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- [`uv`](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Clone and navigate
git clone <repo-url>
cd VibeGraph

# Install Python dependencies
uv sync

# Install frontend dependencies  
cd src/web && npm install && cd ../..
```

### Running VibeGraph

**1. Index your codebase:**
```bash
uv run python -m vibegraph.indexer.main .
```

**2. Start the backend API:**
```bash
uv run python -m vibegraph.server_api
# API runs on http://localhost:8000
```

**3. Start the frontend:**
```bash
cd src/web && npm run dev
# Visualizer runs on http://localhost:5173
```

**4. (Optional) Run the MCP Server for AI agents:**
```bash
uv run python -m vibegraph.mcp.server
```

## Architecture

```
┌─────────────────┐
│   React Flow    │  ← Visualize the graph
│   (Frontend)    │
└────────┬────────┘
         │ WebSocket (Vibe-Sync)
         │ HTTP (API)
┌────────▼────────┐
│  FastAPI Server │  ← Serve graph data
│  (Backend)      │
└────────┬────────┘
         │
    ┌────▼─────┐
    │  SQLite  │  ← Store structural graph
    │   (DB)   │
    └────▲─────┘
         │
┌────────┴────────┐
│   Tree-sitter   │  ← Parse code into AST
│    (Indexer)    │
└─────────────────┘
```

## MCP Tools (AI Interface)

VibeGraph exposes these tools to AI agents via the MCP protocol:

- **`get_structural_summary(file_path)`**: Get an overview of classes/functions in a file
- **`get_call_stack(node_name, direction, depth)`**: Trace function calls up/down the graph
- **`impact_analysis(file_path)`**: See what breaks if you change this file

## Testing

```bash
# Run all tests
uv run pytest

# Run specific suites
uv run pytest tests/test_parser.py
uv run pytest tests/test_mcp.py
uv run pytest tests/test_api.py
```

## Project Structure

```
VibeGraph/
├── src/vibegraph/
│   ├── indexer/          # Tree-sitter extraction + SQLite
│   ├── mcp/              # MCP Server tools
│   └── server_api.py     # FastAPI backend
├── src/web/              # React + React Flow frontend
├── tests/                # Pytest test suite
└── .antigravityrules     # Project documentation for AI
```

## Contributing

See [`.antigravityrules`](.antigravityrules) for detailed development workflows, architecture decisions, and troubleshooting.

## License

MIT
