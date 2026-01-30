# VibeGraph: The Nervous System MCP

![CI](https://github.com/serguei9090/VibeGraph/actions/workflows/ci.yml/badge.svg)

> **Philosophy**: Structural Truth > Statistical Guessing

VibeGraph is a code intelligence system that treats your codebase as a **nervous system**. Instead of vector embeddings and similarity search, it uses Tree-sitter for AST parsing and SQLite for relational queries. The result? A structural graph that AI agents can query and you can visualize in real-time.

## Features

- **🧠 Structural Indexing**: Tree-sitter AST parsing for high-fidelity extraction of classes, functions, and types.
- **🛡️ Advanced Metadata**: Now indexes **Visibility** (public/private) and **Decorators** (e.g., `@mcp.tool`, `@property`).
- **🔍 MCP Server**: AI-queryable tools for deep code reasoning.
- **⚡ Transitive Impact Analysis**: Trace the "Blast Radius" of a change up to 3 levels deep.
- **🗺️ Map Room**: React Flow visualizer with live updates and force-directed layouts.
- **🧬 Breadcrumb Tracing**: Call stacks include full context paths (`A > B > C`), preventing confusion in deep recursion.
- **📦 Dependency Intelligence**: Automatically categorizes imports into **Internal**, **Third-Party**, and **Standard Library**.
- **🧪 Fully Tested**: Robust Pytest suite covering the parser, MCP tools, and API.

## Supported Languages

VibeGraph uses Tree-sitter for high-fidelity structural extraction. Support levels vary by language:

| Language | Extensions | Support Level | Extracted Features |
| :--- | :--- | :--- | :--- |
| **Python** | `.py` | 🔥 Full | Classes, Functions, Imports, Docstrings, **Decorators**, **Visibility** |
| **JavaScript/TS** | `.js`, `.ts`, `.tsx` | 💎 High | Classes, Functions, Interfaces, Inherits/Implements, **Decorators** |
| **Go** | `.go` | ✅ Solid | Structs, Interfaces, Functions, Methods |
| **Rust** | `.rs` | ✅ Solid | Structs, Traits, Impls, Functions |
| **Java** | `.java` | 🛠️ Generic | Classes, Methods, Inheritance (Base extraction) |
| **C / C++** | `.c`, `.cpp`, `.h` | 🛠️ Generic | Functions, Classes/Structs |
| **C# / Ruby / PHP**| `.cs`, `.rb`, `.php` | 🛠️ Generic | Basic Structural Nodes |

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
# Index the current directory (Use absolute path for best results)
uv run python -m vibegraph.indexer.main $PWD
```
This creates a `vibegraph_context/vibegraph.db` file containing the semantic relational graph.

**2. Start the backend API:**
```bash
uv run python -m vibegraph.server_api
# API runs on http://localhost:8000
```

**3. Start the Web Map Room:**
```bash
cd src/web && npm run dev
# Visualizer runs on http://localhost:5173
```

**4. Start the MCP Server (for Claude Desktop/AI Agents):**
```bash
uv run python -m vibegraph.mcp.server
```

## MCP Tools (The Intelligence Layer)

VibeGraph exposes a **Model Context Protocol (MCP)** server that allows AI agents to "think" semantically about your code.

- **`vibegraph_get_structural_summary(file_path)`**: Returns all definitions in a file with visibility icons (`[f]`, `[c]`), signatures, and decorators.
- **`vibegraph_get_call_stack(node_name, direction, depth)`**: Traces calls with breadcrumb paths (e.g., `A > B > C`) to maintain context in deep traces.
- **`vibegraph_impact_analysis(file_path)`**: **Transitive Impact Analysis**. Returns Direct (L1), Secondary (L2), and Deep (L3) impacts of changing a file.
- **`vibegraph_get_dependencies(file_path)`**: Categorizes dependencies into Internal modules, 3rd party packages, and standard library.
- **`vibegraph_find_references(symbol_name, scope_path)`**: Find all call-sites and references to a specific function or class across the project.
- **`vibegraph_search_by_signature(pattern, scope_path)`**: Semantic search using GLOb patterns in signatures (e.g., `%IndexerDB%` to find all functions using that type).
- **`vibegraph_reindex_project(path)`**: Trigger a refresh of the index for a specific directory or file.

## Map Room Intelligence

The Web Visualizer (Map Room) includes interactive panels to filter and analyze the codebase:

### Visual Indicators (Legend)
- <span style="display: inline-block; width: 8px; height: 8px; background: #6366f1; border-radius: 2px;"></span> **Function**: Standard logic blocks.
- <span style="display: inline-block; width: 8px; height: 8px; background: #a855f7; border-radius: 2px;"></span> **Class**: Blueprints/Objects.
- <span style="display: inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 2px;"></span> **Interface**: Type definitions and contracts.
- **🔒 Icon**: Private symbol (internal use).
- **🌐 Icon**: Public/Exported symbol.
- **@badge**: Decorators/Annotations (e.g., `@mcp.tool`).

### Control Panels
- **Type Filters**: Toggle visibility of Functions, Classes, and Interfaces to focus on specific architectural layers.
- **Show Private**: Disable to hide internal implementation details and focus on the public API.
- **Deep Impact Mode**: When enabled, clicking a node highlights its **Transitive Impact** (Blast Radius). This shows every function that would need to be checked if that specific node is modified, up to 3 levels deep.

## Project Structure

```
VibeGraph/
├── src/vibegraph/
│   ├── indexer/          # Tree-sitter extraction + Semantic Resolver
│   ├── mcp/              # MCP Server tools + Pydantic Models
│   └── server_api.py     # FastAPI + WebSocket backend
├── src/web/              # React + React Flow frontend
├── vibegraph_context/    # Database storage (git-ignored)
└── tests/                # Pytest test suite (30+ tests)
```

## License

MIT
