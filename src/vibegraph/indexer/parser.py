import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from tree_sitter import Language, Node, Parser, Tree
from tree_sitter_languages import get_language, get_parser

from vibegraph.indexer.db import Edge
from vibegraph.indexer.db import Node as DBNode
from vibegraph.indexer.resolver import ModuleResolver


class LanguageParser(ABC):
    def __init__(self, language_name: str, resolver: ModuleResolver | None = None):
        self.language: Language = get_language(language_name)
        self.parser: Parser = get_parser(language_name)
        self.resolver = resolver

    def parse(self, source_code: bytes) -> Tree:
        return self.parser.parse(source_code)

    def _get_text(self, node: Node | None) -> str:
        """Extract text from a tree-sitter node."""
        if node is None:
            return ""
        return node.text.decode("utf-8")

    def _get_id(self, file_path: str, name: str, kind: str | None = None) -> str:
        """Generate a unique ID for a node."""
        if kind == "module":
            # Modules are identified by their canonical name across the project
            return hashlib.md5(f"module::{name}".encode()).hexdigest()
        return hashlib.md5(f"{file_path}::{name}".encode()).hexdigest()

    def _create_node(
        self,
        node_id: str,
        name: str,
        kind: Any,
        file_path: str,
        node: Node | None,  # Changed to allow None for virtual nodes
        signature: str | None = None,
        docstring: str | None = None,
        decorators: list[str] | None = None,
        visibility: str | None = None,
    ) -> DBNode:
        """Create a DBNode with common fields."""
        start_line = node.start_point[0] + 1 if node else 0
        end_line = node.end_point[0] + 1 if node else 0
        return DBNode(
            id=node_id,
            name=name,
            kind=kind,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            docstring=docstring,
            decorators=decorators,
            visibility=visibility,
        )

    def _create_edge(self, from_id: str, to_id: str, relation: Any = "defines") -> Edge:
        """Create an edge between two nodes."""
        return Edge(from_node_id=from_id, to_node_id=to_id, relation_type=relation)

    @abstractmethod
    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        """Extract nodes and edges from source code."""
        pass


@dataclass
class ParserContext:
    file_path: str
    nodes: list[DBNode]
    edges: list[Edge]
    file_module_id: str


class PythonParser(LanguageParser):
    """Parser for Python files."""

    def __init__(self, resolver: ModuleResolver | None = None):
        super().__init__("python", resolver)

    def _extract_docstring(self, node: Node) -> str | None:
        body_node = node.child_by_field_name("body")
        if not body_node:
            return None

        for child in body_node.children:
            if child.type == "expression_statement":
                first_child = child.children[0]
                if first_child.type == "string":
                    return self._get_text(first_child).strip("\"'")
            elif child.type == "comment":
                continue
            else:
                break
        return None

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        module_name = file_path.split("/")[-1].replace(".py", "")
        if self.resolver:
            canonical = self.resolver.get_module_name(file_path)
            if canonical:
                module_name = canonical

        file_module_id = self._get_id(file_path, module_name, kind="module")
        nodes.append(
            self._create_node(file_module_id, module_name, "module", file_path, tree.root_node)
        )

        ctx = ParserContext(file_path, nodes, edges, file_module_id)
        self._traverse(tree.root_node, file_module_id, ctx)

        return nodes, edges

    def _traverse(
        self,
        node: Node,
        parent_id: str | None,
        ctx: ParserContext,
        decorators: list[str] | None = None,
    ):
        # Special handling for decorated definitions
        if node.type == "decorated_definition":
            self._handle_decorated(node, parent_id, ctx)
            return

        node_id = None

        # 1. Definitions
        if node.type in ("function_definition", "class_definition"):
            node_id = self._handle_definition(node, parent_id, ctx, decorators)

        # 2. Calls
        elif parent_id and node.type == "call":
            self._handle_call(node, parent_id, ctx)

        # 3. Imports
        elif node.type in ("import_statement", "import_from_statement"):
            self._handle_import(node, ctx)

        # Recurse
        current_scope_id = node_id if node_id else parent_id
        for child in node.children:
            self._traverse(child, current_scope_id, ctx)

    def _handle_decorated(self, node: Node, parent_id: str | None, ctx: ParserContext):
        current_decorators = []
        def_node = None
        for child in node.children:
            if child.type == "decorator":
                current_decorators.append(self._get_text(child))
            elif child.type in ("function_definition", "class_definition"):
                def_node = child

        if def_node:
            self._traverse(def_node, parent_id, ctx, current_decorators)

    def _handle_definition(
        self, node: Node, parent_id: str | None, ctx: ParserContext, decorators: list[str] | None
    ) -> str | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_text(name_node)
        node_id = self._get_id(ctx.file_path, name)
        kind = "function" if node.type == "function_definition" else "class"

        params_node = node.child_by_field_name("parameters")
        signature = self._get_text(params_node) if params_node else None
        docstring = self._extract_docstring(node)

        # Determine visibility
        visibility = "public"
        if name.startswith("_") and not name.startswith("__"):
            visibility = "private"

        ctx.nodes.append(
            self._create_node(
                node_id,
                name,
                kind,
                ctx.file_path,
                node,
                signature,
                docstring,
                decorators=decorators,
                visibility=visibility,
            )
        )

        if parent_id:
            ctx.edges.append(
                Edge(from_node_id=parent_id, to_node_id=node_id, relation_type="defines")
            )
        return node_id

    def _handle_call(self, node: Node, parent_id: str, ctx: ParserContext):
        func_node = node.child_by_field_name("function")
        if func_node:
            called_name = self._get_text(func_node)
            target_id = self._get_id(ctx.file_path, called_name)
            ctx.edges.append(
                Edge(from_node_id=parent_id, to_node_id=target_id, relation_type="calls")
            )

    def _handle_import(self, node: Node, ctx: ParserContext):
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    module_name = self._get_text(child)
                    self._add_import_edge(module_name, node, ctx)
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        module_name = self._get_text(name_node)
                        self._add_import_edge(module_name, node, ctx)

        elif node.type == "import_from_statement":
            module_name_node = node.child_by_field_name("module_name")
            if module_name_node:
                module_name = self._get_text(module_name_node)
                # Handle `from . import foo` (relative imports)
                # For now, we treat relative imports as part of the module name
                self._add_import_edge(module_name, node, ctx)

    def _add_import_edge(self, module_name: str, import_node: Node, ctx: ParserContext):
        resolved_path = None
        if self.resolver:
            # The resolver should handle relative imports based on ctx.file_path
            resolved_path = self.resolver.resolve(module_name, ctx.file_path)

        module_path = resolved_path if resolved_path else "external"

        module_id = self._get_id(module_path, module_name, kind="module")

        # Check if this module node already exists to avoid duplicates
        # This is a simple check, a more robust solution might involve a set of module_ids
        if not any(n.id == module_id for n in ctx.nodes):
            ctx.nodes.append(
                self._create_node(module_id, module_name, "module", module_path, import_node)
            )

        ctx.edges.append(self._create_edge(ctx.file_module_id, module_id, "imports"))


class JavaScriptParser(LanguageParser):
    """Parser for JavaScript and JSX files."""

    def __init__(self, resolver: ModuleResolver | None = None):
        super().__init__("javascript", resolver)

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        module_name = file_path.split("/")[-1]
        if self.resolver:
            canonical = self.resolver.get_module_name(file_path)
            if canonical:
                module_name = canonical

        file_module_id = self._get_id(file_path, module_name, kind="module")
        nodes.append(
            self._create_node(file_module_id, module_name, "module", file_path, tree.root_node)
        )

        def traverse(node: Node, parent_id: str | None = None, is_exported: bool = False):
            # Check for export statement
            if node.type == "export_statement":
                for child in node.children:
                    traverse(child, parent_id, is_exported=True)
                return

            node_id = None
            visibility = "exported" if is_exported else "internal"

            # Function declarations, arrow functions, class methods
            if node.type in (
                "function_declaration",
                "arrow_function",
                "function",
                "method_definition",
            ):
                name_node = node.child_by_field_name("name")
                name = self._get_text(name_node) if name_node else "<anonymous>"

                node_id = self._get_id(file_path, name)
                kind = "function"

                params_node = node.child_by_field_name("parameters")
                signature = self._get_text(params_node) if params_node else None

                nodes.append(
                    self._create_node(
                        node_id, name, kind, file_path, node, signature, visibility=visibility
                    )
                )

                if parent_id:
                    edges.append(self._create_edge(parent_id, node_id))

            # Class declarations
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)

                    nodes.append(
                        self._create_node(
                            node_id, name, "class", file_path, node, visibility=visibility
                        )
                    )

                    if parent_id:
                        edges.append(self._create_edge(parent_id, node_id))

                    # Check for inheritance
                    class_heritage = node.child_by_field_name("class_heritage")
                    if class_heritage:
                        extends_clause = class_heritage.children[0]
                        if extends_clause.type == "extends_clause":
                            base_class_node = extends_clause.children[1]
                            base_class_name = self._get_text(base_class_node)
                            # Create a virtual node for external dependency or best effort link
                            base_id = self._get_id(file_path, base_class_name)
                            edges.append(
                                Edge(
                                    from_node_id=node_id,
                                    to_node_id=base_id,
                                    relation_type="inherits",
                                )
                            )

            # Function Calls
            if parent_id and node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node:
                    called_name = self._get_text(func_node)
                    # Simplified: just create a relationship
                    # We might need a "call_target" node if it's external
                    # For now just use hash of name as potential ID
                    target_id = self._get_id(file_path, called_name)
                    edges.append(
                        Edge(from_node_id=parent_id, to_node_id=target_id, relation_type="calls")
                    )

            # Imports
            if node.type == "import_statement":
                source_node = node.child_by_field_name("source")
                if source_node:
                    # module_name = self._get_text(source_node).strip("'\"")
                    # Create a module node for the import
                    # module_id = self._get_id(file_path, module_name)
                    # For imports, we often link the FILE to the module, but we don't have a
                    # file node here easily unless we made one.
                    pass

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id, is_exported=is_exported)

        traverse(tree.root_node, file_module_id)
        return nodes, edges


class TypeScriptParser(LanguageParser):
    """Parser for TypeScript and TSX files."""

    def __init__(self, language="typescript", resolver: ModuleResolver | None = None):
        super().__init__(language, resolver)

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        module_name = file_path.split("/")[-1]
        if self.resolver:
            canonical = self.resolver.get_module_name(file_path)
            if canonical:
                module_name = canonical

        file_module_id = self._get_id(file_path, module_name, kind="module")
        nodes.append(
            self._create_node(file_module_id, module_name, "module", file_path, tree.root_node)
        )

        def traverse(
            node: Node,
            parent_id: str | None = None,
            is_exported: bool = False,
            decorators: list[str] | None = None,
        ):
            # Check for export statement in TS
            if node.type == "export_statement":
                # Handle exported declarations
                for child in node.children:
                    traverse(child, parent_id, is_exported=True)
                return

            # Decorators in TS
            if node.type == "decorator":
                # We often get decorators as siblings or children depending on structure,
                # but standard TS grammar: (decorator) (class_declaration)
                # This might need refinement based on exact tree-sitter-typescript grammar
                pass

            node_id = None
            visibility = "exported" if is_exported else "internal"

            # Function declarations, arrow functions, methods
            if node.type in (
                "function_declaration",
                "arrow_function",
                "function",
                "method_definition",
                "method_signature",
            ):
                name_node = node.child_by_field_name("name")
                name = self._get_text(name_node) if name_node else "<anonymous>"

                node_id = self._get_id(file_path, name)
                kind = "function"

                params_node = node.child_by_field_name("parameters")
                signature = self._get_text(params_node) if params_node else None

                nodes.append(
                    self._create_node(
                        node_id, name, kind, file_path, node, signature, visibility=visibility
                    )
                )

                if parent_id:
                    edges.append(self._create_edge(parent_id, node_id))

            # Class, interface declarations
            elif node.type in ("class_declaration", "interface_declaration"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)
                    kind = "interface" if node.type == "interface_declaration" else "class"

                    nodes.append(
                        self._create_node(
                            node_id, name, kind, file_path, node, visibility=visibility
                        )
                    )

                    if parent_id:
                        edges.append(self._create_edge(parent_id, node_id))

                    # Check for inheritance (extends) and implementation (implements)
                    class_heritage = node.child_by_field_name("class_heritage")
                    if class_heritage:
                        for child in class_heritage.children:
                            if child.type == "extends_clause":
                                for type_node in child.children:
                                    if type_node.type == "type_identifier":
                                        base_name = self._get_text(type_node)
                                        base_id = self._get_id(file_path, base_name)
                                        edges.append(
                                            Edge(
                                                from_node_id=node_id,
                                                to_node_id=base_id,
                                                relation_type="inherits",
                                            )
                                        )
                            elif child.type == "implements_clause":
                                for type_node in child.children:
                                    if type_node.type == "type_identifier":
                                        interface_name = self._get_text(type_node)
                                        interface_id = self._get_id(file_path, interface_name)
                                        edges.append(
                                            Edge(
                                                from_node_id=node_id,
                                                to_node_id=interface_id,
                                                relation_type="implements",
                                            )
                                        )

            # Function Calls
            if parent_id and node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node:
                    called_name = self._get_text(func_node)
                    if "." in called_name:
                        called_name = called_name.split(".")[-1]

                    target_id = self._get_id(file_path, called_name)
                    edges.append(
                        Edge(from_node_id=parent_id, to_node_id=target_id, relation_type="calls")
                    )

            # Imports
            if node.type == "import_statement":
                source_node = node.child_by_field_name("source")
                if source_node:
                    # module_name = self._get_text(source_node).strip("'\"")
                    pass

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node, file_module_id)
        return nodes, edges


class GoParser(LanguageParser):
    """Parser for Go files."""

    def __init__(self, resolver: ModuleResolver | None = None):
        super().__init__("go", resolver)

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        module_name = file_path.split("/")[-1]
        if self.resolver:
            canonical = self.resolver.get_module_name(file_path)
            if canonical:
                module_name = canonical

        file_module_id = self._get_id(file_path, module_name, kind="module")
        nodes.append(
            self._create_node(file_module_id, module_name, "module", file_path, tree.root_node)
        )

        def traverse(node: Node, parent_id: str | None = None):
            node_id = None

            # Function declarations, methods
            if node.type in ("function_declaration", "method_declaration"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)

                    params_node = node.child_by_field_name("parameters")
                    signature = self._get_text(params_node) if params_node else None

                    nodes.append(
                        self._create_node(node_id, name, "function", file_path, node, signature)
                    )

                    if parent_id:
                        edges.append(self._create_edge(parent_id, node_id))

            # Type declarations (struct, interface)
            elif node.type == "type_declaration":
                type_spec = node.child_by_field_name("type")
                if type_spec:
                    name_node = type_spec.child_by_field_name("name")
                    if name_node:
                        name = self._get_text(name_node)
                        node_id = self._get_id(file_path, name)
                        kind = "interface" if type_spec.type == "interface_type" else "struct"

                        nodes.append(self._create_node(node_id, name, kind, file_path, node))

                        if parent_id:
                            edges.append(self._create_edge(parent_id, node_id))

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node, file_module_id)
        return nodes, edges


class RustParser(LanguageParser):
    """Parser for Rust files."""

    def __init__(self, resolver: ModuleResolver | None = None):
        super().__init__("rust", resolver)

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        module_name = file_path.split("/")[-1]
        if self.resolver:
            canonical = self.resolver.get_module_name(file_path)
            if canonical:
                module_name = canonical

        file_module_id = self._get_id(file_path, module_name, kind="module")
        nodes.append(
            self._create_node(file_module_id, module_name, "module", file_path, tree.root_node)
        )

        def traverse(node: Node, parent_id: str | None = None):
            node_id = None

            # Function items
            if node.type == "function_item":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)

                    params_node = node.child_by_field_name("parameters")
                    signature = self._get_text(params_node) if params_node else None

                    nodes.append(
                        self._create_node(node_id, name, "function", file_path, node, signature)
                    )

                    if parent_id:
                        edges.append(self._create_edge(parent_id, node_id))

            # Struct, trait, impl declarations
            elif node.type in ("struct_item", "trait_item", "impl_item"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)
                    kind: Any = "class"
                    if node.type == "trait_item":
                        kind = "trait"
                    elif node.type == "struct_item":
                        kind = "struct"
                    elif node.type == "impl_item":
                        kind = "impl"

                    nodes.append(self._create_node(node_id, name, kind, file_path, node))

                    if parent_id:
                        edges.append(self._create_edge(parent_id, node_id))

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node, file_module_id)
        return nodes, edges


class GenericParser(LanguageParser):
    """Generic parser for languages with basic function/class extraction."""

    def __init__(self, language: str, resolver: ModuleResolver | None = None):
        super().__init__(language, resolver)
        self.language_name = language

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        module_name = file_path.split("/")[-1]
        if self.resolver:
            canonical = self.resolver.get_module_name(file_path)
            if canonical:
                module_name = canonical

        file_module_id = self._get_id(file_path, module_name, kind="module")
        nodes.append(
            self._create_node(file_module_id, module_name, "module", file_path, tree.root_node)
        )

        # Common node types across C-like languages
        function_types = {
            "function_definition",
            "function_declaration",
            "method_declaration",
            "function_item",
            "method_definition",
        }
        class_types = {
            "class_definition",
            "class_declaration",
            "struct_declaration",
            "interface_declaration",
            "trait_item",
        }

        def traverse(node: Node, parent_id: str | None = None):
            node_id = None

            if node.type in function_types:
                name_node = node.child_by_field_name("name") or node.child_by_field_name(
                    "declarator"
                )
                if name_node:
                    # For C/C++, might need to extract from declarator
                    name_text = self._get_text(name_node)
                    # Simple extraction - get first identifier
                    name = (
                        name_text.split("(")[0].strip().split()[-1]
                        if "(" in name_text
                        else name_text
                    )

                    node_id = self._get_id(file_path, name)

                    nodes.append(self._create_node(node_id, name, "function", file_path, node))

                    if parent_id:
                        edges.append(self._create_edge(parent_id, node_id))

            elif node.type in class_types:
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)

                    nodes.append(self._create_node(node_id, name, "class", file_path, node))

                    if parent_id:
                        edges.append(self._create_edge(parent_id, node_id))

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node, file_module_id)
        return nodes, edges


class ParserFactory:
    @staticmethod
    def get_parser(file_path: str, resolver: ModuleResolver | None = None) -> LanguageParser | None:
        if file_path.endswith(".py"):
            return PythonParser(resolver)
        elif file_path.endswith((".js", ".jsx")):
            return JavaScriptParser(resolver)
        elif file_path.endswith(".ts"):
            return TypeScriptParser("typescript", resolver)
        elif file_path.endswith(".tsx"):
            return TypeScriptParser("tsx", resolver)
        elif file_path.endswith(".go"):
            return GoParser(resolver)
        elif file_path.endswith(".rs"):
            return RustParser(resolver)
        elif file_path.endswith(".java"):
            return GenericParser("java", resolver)
        elif file_path.endswith((".c", ".h")):
            return GenericParser("c", resolver)
        elif file_path.endswith((".cpp", ".cc", ".cxx", ".hpp")):
            return GenericParser("cpp", resolver)
        elif file_path.endswith(".cs"):
            return GenericParser("c_sharp", resolver)
        elif file_path.endswith(".rb"):
            return GenericParser("ruby")
        elif file_path.endswith(".php"):
            return GenericParser("php")
        return None
