# VibeGraph: The Nervous System MCP

**Philosophy**: Structural Truth > Statistical Guessing  
**Status**: Production-Ready Prototype  
**Target**: 100% Vibe Coding in Antigravity

---

## Project Overview

VibeGraph is a code intelligence system that treats codebases as **nervous systems** rather than text documents. It uses Tree-sitter for AST parsing and SQLite for relational storage to create a structural graph that AI agents can query and visualize in real-time.

### Core Philosophy
- **No Vector Search**: We use structural parsing, not embeddings
- **Relational over Statistical**: SQLite graph queries, not similarity search
- **Real-time Sync**: Watchdog + WebSocket for live updates (Vibe-Sync)
- **Visual Intelligence**: React Flow "Map Room" for exploring code structure

---

## Architecture

```
VibeGraph/
├── src/vibegraph/
│   ├── indexer/          # Python: Tree-sitter extraction + SQLite
│   │   ├── db.py         # IndexerDB class (schema, upsert, queries)
│   │   ├── parser.py     # PythonParser (AST traversal)
│   │   ├── main.py       # CLI entry point
│   │   ├── watcher.py    # File watcher (watchdog)
│   │   └── schema.sql    # Database schema
│   ├── mcp/              # Python: MCP Server tools
│   │   └── server.py     # FastMCP app (get_call_stack, impact_analysis, get_structural_summary)
│   └── server_api.py     # FastAPI backend (serves graph to frontend)
├── src/web/              # TypeScript: Vite + React + React Flow
│   └── src/App.tsx       # Main visualizer component
├── tests/                # Pytest test suite
│   ├── test_parser.py    # Indexer tests
│   ├── test_mcp.py       # MCP tools tests
│   └── test_api.py       # API endpoint tests
├── pyproject.toml        # Python dependencies (uv)
├── ruff.toml             # Python linting
└── biome.json            # JS/TS linting
```

---

## Development Workflows

### 1. Initial Setup
```bash
# Install dependencies (Python 3.11)
uv sync

# Install frontend dependencies
cd src/web && npm install
```

### 2. Running the System

**Backend API** (serves graph + Vibe-Sync):
```bash
uv run python -m vibegraph.server_api
# Runs on http://localhost:8000
```

**Frontend** (visualizer):
```bash
cd src/web && npm run dev
# Runs on http://localhost:5173
```

**MCP Server** (for AI agents):
```bash
uv run python -m vibegraph.mcp.server
```

**Indexer CLI** (one-shot indexing):
```bash
uv run python -m vibegraph.indexer.main <directory>
```

**File Watcher** (live indexing):
```bash
uv run python -m vibegraph.indexer.watcher <directory>
```

### 3. Testing
```bash
# Run all tests
uv run pytest

# Run specific test suites
uv run pytest tests/test_parser.py
uv run pytest tests/test_mcp.py
uv run pytest tests/test_api.py
```

### 4. Linting
```bash
# Python
uv run ruff check .
uv run ruff format .

# TypeScript/JavaScript (in src/web)
npm run lint
```

---

## Key Technical Decisions

### Python Version
- **Target**: Python 3.11+
- **Why**: We downgraded `tree-sitter` to `0.21.3` for Windows compatibility with `tree-sitter-languages==1.10.2`

### Database
- **SQLite** for simplicity and portability
- Schema: `nodes` (functions, classes) + `edges` (calls, defines, inherits)
- Content-addressable IDs: `md5(file_path::symbol_name)`

### Parser Status
- **Supported**: Python (functions, classes, docstrings, basic calls)
- **Planned**: JavaScript/TypeScript (extend `ParserFactory`)

### Vibe-Sync Implementation
- `watchdog` detects file changes
- Triggers re-indexing via `IndexerDB`
- FastAPI broadcasts "refresh" via WebSocket
- React frontend auto-fetches updated graph

---

## Common Tasks

### Adding a New Language
1. Add parser in `src/vibegraph/indexer/parser.py` (extend `LanguageParser`)
2. Update `ParserFactory.get_parser()` to recognize file extension
3. Add test in `tests/test_parser.py`

### Adding a New MCP Tool
1. Define `@mcp.tool()` in `src/vibegraph/mcp/server.py`
2. Query `IndexerDB` for required data
3. Add test in `tests/test_mcp.py`

### Improving the Visualizer
1. Edit `src/web/src/App.tsx`
2. Rebuild with `npm run build`
3. Consider adding layout algorithms (dagre, elkjs)

---

## Deployment Notes

### Production Checklist
- [ ] Index production codebase with `indexer.main`
- [ ] Run `server_api.py` on production server (consider Docker)
- [ ] Build frontend with `npm run build` in `src/web`
- [ ] Serve frontend static files via nginx/similar
- [ ] Configure CORS in `server_api.py` for production domain
- [ ] Set up file watcher as background service (systemd/supervisor)

### Environment Variables (Recommended)
- `VIBEGRAPH_DB_PATH`: Path to `vibegraph.db` (default: `./vibegraph.db`)
- `VIBEGRAPH_WATCH_DIR`: Directory to watch (default: `.`)
- `API_HOST`: Backend host (default: `0.0.0.0`)
- `API_PORT`: Backend port (default: `8000`)

---

## Troubleshooting

### "No such table: nodes"
- Run indexer at least once to create the database: `uv run python -m vibegraph.indexer.main .`

### Tree-sitter Import Errors
- Ensure `tree-sitter==0.21.3` (not 0.22+) for Windows compatibility
- Check `pyproject.toml` dependencies

### Frontend Can't Connect to Backend
- Verify backend is running on `http://localhost:8000`
- Check CORS settings in `server_api.py`
- Update `API_URL` in `App.tsx` if needed

### Vibe-Sync Not Working
- Ensure backend started with `lifespan` context (auto-starts watcher)
- Check WebSocket connection in browser DevTools
- Verify file changes are triggering `watchdog` events

---

## Project Principles for AI Sessions

1. **Always read `project.md`** first for context and philosophy
2. **Respect the stack**: Python backend, TypeScript frontend, SQLite storage
3. **Test everything**: Each component has tests (`tests/`)
4. **Lint before commit**: Use `ruff` and `biome`
5. **Update artifacts**: Keep `task.md`, `implementation_plan.md`, `walkthrough.md` in sync
6. **Structural thinking**: Code is a circuit board, not a document
