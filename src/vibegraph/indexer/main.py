import os
import sys
from pathlib import Path

from vibegraph.indexer.db import IndexerDB
from vibegraph.indexer.parser import ParserFactory


def index_file(db: IndexerDB, file_path: str):
    """Index a single file."""
    try:
        abs_path = str(Path(file_path).resolve())
        parser = ParserFactory.get_parser(abs_path)
        if not parser:
            print(f"Skipping {file_path} (unsupported language)")
            return

        with open(abs_path, "rb") as f:
            source_code = f.read()

        print(f"Indexing {file_path}...")
        nodes, edges = parser.extract(abs_path, source_code)

        # Clear old data for this file
        db.clear_file(abs_path)

        # Insert new data
        for node in nodes:
            db.upsert_node(node)
        
        for edge in edges:
            db.upsert_edge(edge)

        print(f"  -> Extracted {len(nodes)} nodes, {len(edges)} edges.")

    except Exception as e:
        print(f"Error indexing {file_path}: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m vibegraph.indexer.main <directory_or_file>")
        sys.exit(1)

    target_path = Path(sys.argv[1])
    db = IndexerDB()

    if target_path.is_file():
        index_file(db, str(target_path))
    elif target_path.is_dir():
        for root, _, files in os.walk(target_path):
            for file in files:
                full_path = Path(root) / file
                # Skip venvs and hidden files
                if ".venv" in str(full_path) or ".git" in str(full_path):
                    continue
                
                index_file(db, str(full_path))
    else:
        print(f"Path not found: {target_path}")

if __name__ == "__main__":
    main()
