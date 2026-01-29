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
- Python 3.11 or 3.12 (Python 3.13+ not yet supported due to `tree-sitter-languages` compatibility)
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

### MCP Server Configuration

To integrate VibeGraph with AI clients (Claude Desktop, Cline, etc.), add this to your MCP settings file:

**For Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "vibegraph": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/serguei9090/vibegraph",
        "vibegraph-mcp"
      ]
    }
  }
}
```

**For local development** (using your local clone):
```json
{
  "mcpServers": {
    "vibegraph": {
      "command": "uv",
      "args": [
        "--directory",
        "I:/01-Master_Code/Test-Labs/VibeGraph",
        "run",
        "vibegraph-mcp"
      ]
    }
  }
}
```

> **Note**: 
> - Replace `YOUR_USERNAME/vibegraph` with your actual GitHub repository path
> - Make sure to index your codebase first (`uv run python -m vibegraph.indexer.main .`) before querying via MCP
> - The MCP server will only have access to the indexed database in the current directory

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

VibeGraph exposes a **Model Context Protocol (MCP) server** that AI agents can query to understand your codebase structure. Once your code is indexed, AI can:

### Query Tools

**`get_structural_summary(file_path)`**
- Returns all functions and classes in a file with signatures and line numbers
- Example: `get_structural_summary("src/vibegraph/indexer/db.py")`
- Output: List of classes (`IndexerDB`), methods, and their signatures

**`get_call_stack(node_name, file_path?, direction, depth)`**
- Traces function calls up (who calls this?) or down (what does this call?)
- `direction`: `"up"` (callers), `"down"` (callees), or `"both"`
- `depth`: How many levels to traverse (default: 1)
- Example: `get_call_stack("upsert_node", direction="up", depth=2)`
- Output: Tree showing all functions that call `upsert_node`

**`impact_analysis(file_path)`**
- Shows what other files/functions depend on this file
- Identifies breaking changes before you make them
- Example: `impact_analysis("src/vibegraph/indexer/db.py")`
- Output: List of dependent files and specific functions affected

### Workflow Integration

```python
# AI Agent Workflow Example:
# 1. Understand a file's structure
summary = get_structural_summary("parser.py")

# 2. Trace how a function is used
callers = get_call_stack("extract", direction="up", depth=3)

# 3. Check impact before refactoring
impact = impact_analysis("parser.py")
```

### Current Limitations
- **Indexing**: Must be done via CLI (`python -m vibegraph.indexer.main .`) before querying
- **Search**: Currently tool-based; full-text search via MCP coming soon
- **Language Support**: Python only (JS/TS planned)

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

See [`mainrule.md`](.agent/rules/mainrule.md) for detailed development workflows, architecture decisions, and troubleshooting.

## License

MIT
