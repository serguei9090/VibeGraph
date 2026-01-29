import os
import sys
from pathlib import Path

from vibegraph.indexer.db import IndexerDB
from vibegraph.indexer.parser import ParserFactory


def index_file(db: IndexerDB, file_path: str, verbose: bool = True):
    """Index a single file."""
    try:
        abs_path = str(Path(file_path).resolve())
        parser = ParserFactory.get_parser(abs_path)
        if not parser:
            if verbose:
                print(f"Skipping {file_path} (unsupported language)")
            return

        with open(abs_path, "rb") as f:
            source_code = f.read()

        if verbose:
            print(f"Indexing {file_path}...")
        nodes, edges = parser.extract(abs_path, source_code)

        # Clear old data for this file
        db.clear_file(abs_path)

        # Insert new data
        for node in nodes:
            db.upsert_node(node)
        
        for edge in edges:
            db.upsert_edge(edge)

        if verbose:
            print(f"  -> Extracted {len(nodes)} nodes, {len(edges)} edges.")

    except Exception as e:
        if verbose:
            print(f"Error indexing {file_path}: {e}")


import pathspec

def load_gitignore(root_path: Path) -> pathspec.PathSpec | None:
    """Load .gitignore from the root path if it exists."""
    gitignore_path = root_path / ".gitignore"
    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                return pathspec.PathSpec.from_lines("gitignore", f)
        except Exception as e:
            print(f"Warning: Failed to load .gitignore: {e}")
    return None

def reindex_all(db: IndexerDB, target_path_str: str, verbose: bool = True):
    """Reindex a file or directory recursively."""
    target_path = Path(target_path_str).resolve()
    
    # default skips
    skip_dirs = {".git", ".venv", "node_modules", "__pycache__", ".ruff_cache", "dist", "build"}
    
    spec = None
    if target_path.is_dir():
         spec = load_gitignore(target_path)

    if target_path.is_file():
        index_file(db, str(target_path), verbose=verbose)
    elif target_path.is_dir():
        for root, dirs, files in os.walk(target_path):
            current_root = Path(root)
            
            # 1. Prune standard noisy directories first (optimization)
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
            
            # 2. Filter files using gitignore
            for file in files:
                full_path = current_root / file
                
                # Check gitignore if available
                if spec:
                    try:
                        rel_path = full_path.relative_to(target_path)
                        if spec.match_file(str(rel_path)):
                            if verbose:
                                # Optional: verify strictly necessary debug to avoid noise
                                pass 
                            continue
                    except ValueError:
                        # Path not relative to target_path (shouldn't happen with walk)
                        pass
                
                index_file(db, str(full_path), verbose=verbose)
    else:
        if verbose:
            print(f"Path not found: {target_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m vibegraph.indexer.main <directory_or_file>")
        sys.exit(1)

    db = IndexerDB()
    reindex_all(db, sys.argv[1])

if __name__ == "__main__":
    main()
