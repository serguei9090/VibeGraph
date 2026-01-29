# VibeGraph: The Nervous System MCP

> **Philosophy**: Structural Truth > Statistical Guessing

VibeGraph is a code intelligence system that treats your codebase as a **nervous system**. Instead of vector embeddings and similarity search, it uses Tree-sitter for AST parsing and SQLite for relational queries. The result? A structural graph that AI agents can query and you can visualize in real-time.

## Features

- **🧠 Structural Indexing**: Tree-sitter AST parsing for multiple languages.
- **🔍 MCP Server**: AI-queryable tools (`get_call_stack`, `impact_analysis`, `get_structural_summary`).
- **🗺️ Map Room**: React Flow visualizer with live updates.
- **⚡ Vibe-Sync**: Real-time WebSocket updates when code changes.
- **🧪 Fully Tested**: Pytest suite for indexer, MCP tools, and API.
- **🛡️ Windows Friendly**: Built-in support for Windows console encoding and path normalization.

## Supported Languages

VibeGraph uses specific parsers for high-fidelity extraction:
- **Python**: Full support (Classes, Functions, Imports, Docstrings).
- **JavaScript / TypeScript**: Classes, Functions, Interfaces, Inherits/Implements.
- **Go**: Structs, Interfaces, Functions, Methods.
- **Rust**: Structs, Traits, Impls, Functions.
- **C / C++ / Java / C# / Ruby / PHP**: Generic extraction of functions and classes.

## Quick Start

### Prerequisites
- Python 3.11 or 3.12 (Python 3.13+ not yet supported due to `tree-sitter-languages` compatibility).
- Node.js 18+ (for frontend).
- [`uv`](https://github.com/astral-sh/uv) package manager.

### Installation

```bash
# Clone and navigate
git clone https://github.com/serguei9090/VibeGraph.git
cd VibeGraph

# Install Python dependencies
uv sync

# Install frontend dependencies  
cd src/web && npm install && cd ../..
```

### Running VibeGraph

**1. Index your codebase:**
```bash
# Index the current directory
uv run python -m vibegraph.indexer.main .
```
This creates a `vibegraph_context/vibegraph.db` file containing the relational graph.

**2. Start the backend API:**
```bash
uv run python -m vibegraph.server_api
# API runs on http://localhost:8000
```
The server handles the SQLite connection and provides a WebSocket for the visualizer.

**3. Start the Web Map Room:**
```bash
cd src/web && npm run dev
# Visualizer runs on http://localhost:5173
```
Open [http://localhost:5173](http://localhost:5173) in your browser to see the 2D graph of your code. Nodes are color-coded by type (Class, Function, Module) and edges show relationships like `defines`, `calls`, or `imports`.

**4. Start the MCP Server (for Claude Desktop/AI Agents):**
```bash
uv run python -m vibegraph.mcp.server
```

## The Web Map Room

The frontend provides a real-time visualization of your codebase:
- **Automatic Layout**: Nodes are positioned using a force-directed algorithm.
- **Interactive**: Drag nodes, zoom in on clusters, and click elements to see their signatures/metadata.
- **Vibe-Sync**: If you keep the `server_api` running while you edit code or re-index, the graph updates automatically via WebSockets.

## MCP Tools (AI Interface)

VibeGraph exposes a **Model Context Protocol (MCP) server** that AI agents can query.

### Query Tools

- **`get_structural_summary(file_path)`**: Returns all functions/classes in a file with signatures.
- **`get_call_stack(node_name, direction, depth)`**: Traces calls `up` (callers) or `down` (callees).
- **`impact_analysis(file_path)`**: Shows what external code depends on this file.
- **`get_dependencies(file_path)`**: Lists modules and symbols imported by the file.
- **`reindex_project(path)`**: Manually trigger a re-index of a specific path.

## Development

```bash
# Run tests
uv run pytest

# Lint and Format
uv run ruff check .
uv run ruff format .
```

## Project Structure

```
VibeGraph/
├── src/vibegraph/
│   ├── indexer/          # Tree-sitter extraction + SQLite
│   ├── mcp/              # MCP Server tools
│   └── server_api.py     # FastAPI + WebSocket backend
├── src/web/              # React + React Flow frontend
├── vibegraph_context/    # Database storage (git-ignored)
└── tests/                # Pytest test suite
```

## License

MIT
