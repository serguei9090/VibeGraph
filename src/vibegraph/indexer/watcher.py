import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from vibegraph.indexer.db import IndexerDB
from vibegraph.indexer.main import index_file


class CodeChangeHandler(FileSystemEventHandler):
    def __init__(self, db: IndexerDB, on_change: Callable[[], None] | None = None):
        self.db = db
        self.on_change = on_change

    def _notify(self):
        if self.on_change:
            try:
                self.on_change()
            except Exception as e:
                print(f"Error in watcher callback: {e}")

    def on_modified(self, event):
        if event.is_directory:
            return
        print(f"File modified: {event.src_path}")
        index_file(self.db, event.src_path)
        self._notify()

    def on_created(self, event):
        if event.is_directory:
            return
        print(f"File created: {event.src_path}")
        index_file(self.db, event.src_path)
        self._notify()

    def on_deleted(self, event):
        if event.is_directory:
            return
        print(f"File deleted: {event.src_path}")
        self.db.clear_file(event.src_path)
        self._notify()


def start_observer(path: str, db: IndexerDB, callback: Callable[[], None] | None = None) -> Any:
    """Start the observer and return it (non-blocking)."""
    path_obj = Path(path).resolve()
    if not path_obj.exists():
        print(f"Warning: Path not found: {path}")

    event_handler = CodeChangeHandler(db, callback)
    observer = Observer()
    observer.schedule(event_handler, str(path_obj), recursive=True)
    observer.start()
    print(f"VibeGraph Watcher started on {path_obj}")
    return observer


def start_watcher_blocking(path: str):
    """Blocking version for CLI usage."""
    db = IndexerDB()
    observer = start_observer(path, db)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m vibegraph.indexer.watcher <directory>")
    else:
        start_watcher_blocking(sys.argv[1])
