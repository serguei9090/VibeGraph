import os
from pathlib import Path


class ModuleResolver:
    """Resolves language-specific module names to local filesystem paths."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.module_map: dict[str, str] = {}
        self._build_map()

    def _build_map(self):
        """Builds a map of module names to relative file paths."""
        src_dirs = {"src", "lib", "python"}

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            rel_root = Path(root).relative_to(self.project_root)

            for file in files:
                if not file.endswith((".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs")):
                    continue

                rel_path_str = str(rel_root / file).replace("\\", "/")
                name_parts = list(rel_root.parts)
                base_name = file.rsplit(".", 1)[0]

                # Absolute mapping
                self._add_to_map(name_parts, base_name, rel_path_str)

                # Strip src_dir if present
                if name_parts and name_parts[0] in src_dirs:
                    self._add_to_map(name_parts[1:], base_name, rel_path_str)

    def _add_to_map(self, parts: list[str], base_name: str, path: str):
        if base_name == "__init__":
            module_name = ".".join(parts)
        else:
            module_name = ".".join([*parts, base_name])

        if module_name:
            self.module_map[module_name] = path

    def resolve(self, module_name: str, current_file: str | None = None) -> str | None:
        """Resolves a module name to a relative path."""
        if not module_name:
            return None

        if module_name.startswith("."):
            return self._resolve_relative(module_name, current_file)

        return self.module_map.get(module_name)

    def _resolve_relative(self, _module_name: str, current_file: str | None) -> str | None:
        """Basic relative import resolution."""
        if not current_file:
            return None
        # Placeholder for future multi-dot resolution
        return None

    def get_module_name(self, file_path: str) -> str | None:
        """Find the canonical module name for a file path."""
        # Prioritize "clean" names (not starting with src, etc)
        src_dirs = {"src", "lib", "python"}
        candidates = []
        for name, path in self.module_map.items():
            if path == file_path:
                candidates.append(name)

        if not candidates:
            return None

        # Try to find one that doesn't start with src_dirs
        for c in candidates:
            if not any(c.startswith(sd + ".") for sd in src_dirs) and c not in src_dirs:
                return c

        return candidates[0]
