from vibegraph.mcp.server import get_structural_summary, _normalize_path
from pathlib import Path

print("Current working directory:", Path.cwd())
print()

test_paths = [
    "src/vibegraph/mcp/server.py",
    "src\\vibegraph\\mcp\\server.py",
    "I:\\01-Master_Code\\Test-Labs\\VibeGraph\\src\\vibegraph\\mcp\\server.py",
]

for path in test_paths:
    normalized = _normalize_path(path)
    print(f"Input: {path}")
    print(f"Normalized: {normalized}")
    result = get_structural_summary(path)
    print(f"Result: {result[:100]}...")
    print()
