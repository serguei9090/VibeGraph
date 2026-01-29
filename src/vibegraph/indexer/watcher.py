import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from vibegraph.indexer.db import IndexerDB
from vibegraph.indexer.main import index_file


class CodeChangeHandler(FileSystemEventHandler):
    def __init__(self, db: IndexerDB):
        self.db = db

    def on_modified(self, event):
        if event.is_directory:
            return
        # Basic debouncing could be added here
        print(f"File modified: {event.src_path}")
        index_file(self.db, event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        print(f"File created: {event.src_path}")
        index_file(self.db, event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        print(f"File deleted: {event.src_path}")
        self.db.clear_file(event.src_path)


def start_watcher(path: str):
    path_obj = Path(path).resolve()
    if not path_obj.exists():
        print(f"Path not found: {path}")
        return

    db = IndexerDB()
    event_handler = CodeChangeHandler(db)
    observer = Observer()
    observer.schedule(event_handler, str(path_obj), recursive=True)
    observer.start()
    
    print(f"Watching {path_obj} for changes... (Ctrl+C to stop)")
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
        start_watcher(sys.argv[1])
