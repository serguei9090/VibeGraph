-- Represents "Entities" (Functions, Classes, Variables)
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,           -- Unique hash of file_path + name
    name TEXT NOT NULL,
    kind TEXT CHECK(kind IN ('function', 'class', 'module', 'interface', 'variable')),
    file_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    signature TEXT,                -- The code signature for quick reference
    docstring TEXT                 -- Extracted comments for semantic context
);

-- Represents "Neural Connections" (Calls, Imports, Inheritance)
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node_id TEXT,             -- The caller/user
    to_node_id TEXT,               -- The callee/definition
    relation_type TEXT CHECK(relation_type IN ('calls', 'defines', 'inherits', 'references', 'imports')),
    FOREIGN KEY(from_node_id) REFERENCES nodes(id),
    FOREIGN KEY(to_node_id) REFERENCES nodes(id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_file_path ON nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_node_id);
