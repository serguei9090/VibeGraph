# VibeGraph Code Style & UX Principles

## 1. Python (Backend & Indexer)

### Linting & Formatting
- **Standard**: [Ruff](https://beta.ruff.rs/docs/) is the source of truth.
- **Line Length**: 100 characters.
- **Rules**: `E`, `F`, `I`, `N`, `UP`, `B`, `A`, `C4`, `PT`, `RUF`.

### Function & Class Signatures
- **Multi-line Parameters**: For methods or functions with many arguments, use the expanded multi-line format to stay within line length limits:
  ```python
  def __init__(
      self,
      db: IndexerDB,
      on_change: Callable[[], None] | None = None,
      root_path: str = ".",
  ):
  ```
- **Type Hints**: Mandatory for all signatures in `src/vibegraph/`.

### Directory Ignores
- Standard system/tool directories must always be ignored: `.git`, `.venv`, `node_modules`, `__pycache__`, `.ruff_cache`, `dist`, `build`, `vibegraph_context`.

---

## 2. TypeScript & React Flow (Frontend)

### Layout Engine (ELK)
- **3-Tier Hierarchy**: `Root` -> `District` (folder) -> `File` (node) -> `Symbol` (vibeNode).
- **Multi-Column Packing**: Inside file groups, use `elk.algorithm: 'rectpacking'` to create a square-ish grid of symbols instead of long vertical/horizontal lists.
- **Padding**:
  - **File Groups**: Use `top: 55px` (50px header + 5px gap) to prevent symbols from overlapping the filename header.
  - **District Groups**: Use `top: 80px` to make room for large title indicators.

### Component Architecture
- **Memoization**: Always wrap custom node components (`VibeNode`, `DistrictNode`, `FileGroupNode`) in `memo`.
- **Performance**: Use `useCallback` for event handlers like `onNodeClick` or `onEdgeClick` to prevent unnecessary React Flow re-renders.

### Interaction & Selection
- **Neighborhood Highlighting**: Clicking a node highlights its "neighborhood" (the node + directly connected edges + immediate neighbor nodes).
- **Selection State**: Unselected nodes and edges should drop to low opacity (`0.05` to `0.1`) to emphasize the selection.
- **Edge Noise**: 
  - Hide repetitive labels like `defines` by default.
  - Show original relation labels ONLY when the edge or its connects are selected.

---

## 3. UI/UX Aesthetics

### Design System
- **Theme**: Dark Mode only.
- **Surfaces**: Glassmorphism (`backdrop-filter: blur(8px)`, `rgba` backgrounds).
- **Typography**: `Inter` for general UI, `JetBrains Mono` for code symbols and file paths.

### Highlighting
- **Class**: Purple accent (`#a855f7`).
- **Interface**: Green accent (`#10b981`).
- **Function/Default**: Indigo accent (`#6366f1`).
- **Dimmed State**: Nodes should use an opacity drop rather than color whitening/graying to preserve the "map" aesthetics.

### Spatial Organization
- **Top Labels**: District labels (folders) sit *above* their containers (`top: -110px`) to act as architectural landmarks.
- **File Headers**: Integration-style headers for files with full paths and symbol counts.
