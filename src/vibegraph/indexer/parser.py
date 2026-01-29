import hashlib
from abc import ABC, abstractmethod
from typing import Any

from tree_sitter import Language, Node, Parser, Tree
from tree_sitter_languages import get_language, get_parser

from vibegraph.indexer.db import Edge
from vibegraph.indexer.db import Node as DBNode


class LanguageParser(ABC):
    def __init__(self, language_name: str):
        self.language: Language = get_language(language_name)
        self.parser: Parser = get_parser(language_name)

    def parse(self, source_code: bytes) -> Tree:
        return self.parser.parse(source_code)

    def _get_text(self, node: Node | None) -> str:
        """Extract text from a tree-sitter node."""
        if node is None:
            return ""
        return node.text.decode("utf-8")

    def _get_id(self, file_path: str, name: str) -> str:
        """Generate a unique ID for a node."""
        return hashlib.md5(f"{file_path}::{name}".encode()).hexdigest()

    def _create_node(
        self,
        node_id: str,
        name: str,
        kind: Any,
        file_path: str,
        node: Node,
        signature: str | None = None,
        docstring: str | None = None,
    ) -> DBNode:
        """Create a DBNode with common fields."""
        return DBNode(
            id=node_id,
            name=name,
            kind=kind,
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=signature,
            docstring=docstring,
        )

    def _create_edge(self, from_id: str, to_id: str, relation: Any = "defines") -> Edge:
        """Create an edge between two nodes."""
        return Edge(from_node_id=from_id, to_node_id=to_id, relation_type=relation)

    @abstractmethod
    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        """Extract nodes and edges from source code."""
        pass


class PythonParser(LanguageParser):
    def __init__(self):
        super().__init__("python")

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
        file_name = file_path.split("/")[-1]  # Simple basename
        file_module_id = self._get_id(file_path, file_name)
        # Create a node for the whole file/module
        # We use the root node of the tree for location info
        nodes.append(
            self._create_node(file_module_id, file_name, "module", file_path, tree.root_node)
        )

        def traverse(node: Node, parent_id: str | None = None):
            node_id = None

            # 1. Definitions
            if node.type in ("function_definition", "class_definition"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)
                    kind = "function" if node.type == "function_definition" else "class"

                    params_node = node.child_by_field_name("parameters")
                    signature = self._get_text(params_node) if params_node else None
                    docstring = self._extract_docstring(node)

                    nodes.append(
                        self._create_node(
                            node_id, name, kind, file_path, node, signature, docstring
                        )
                    )

                    if parent_id:
                        edges.append(
                            Edge(
                                from_node_id=parent_id, to_node_id=node_id, relation_type="defines"
                            )
                        )

            # 2. Function Calls
            if parent_id and node.type == "call":
                func_node = node.child_by_field_name("function")
                if func_node:
                    # Handle simple calls like foo() or obj.method()
                    called_name = self._get_text(func_node)
                    if "." in called_name:
                        called_name = called_name.split(".")[-1]  # Simple heuristic for method name

                    # Simplification for VibeGraph v1 (as per plan):
                    # We will create a "call" edge from parent_id to a new node representing
                    # the CALLED function.
                    # pass
                    pass

            # 3. Imports
            if node.type in ("import_statement", "import_from_statement"):
                if node.type == "import_statement":
                    for child in node.children:
                        if child.type == "dotted_name":
                            module_name = self._get_text(child)
                            # External modules don't have a file path yet
                            module_id = self._get_id("external", module_name)

                            # Create a virtual node for external module (idempotent if same ID)
                            nodes.append(
                                self._create_node(
                                    module_id, module_name, "module", "external", node
                                )
                            )

                            # Link file -> external module
                            # Use file_module_id as source
                            edges.append(self._create_edge(file_module_id, module_id, "imports"))

                elif node.type == "import_from_statement":
                    module_node = node.child_by_field_name("module_name")
                    if module_node:
                        module_name = self._get_text(module_node)
                        module_id = self._get_id("external", module_name)

                        nodes.append(
                            self._create_node(module_id, module_name, "module", "external", node)
                        )
                        edges.append(self._create_edge(file_module_id, module_id, "imports"))

            # Recurse
            # If we created a node (`node_id`), it becomes the scope for children.
            # If not, we pass the current `parent_id`.
            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        # Start traversal with the file module as the parent
        traverse(tree.root_node, file_module_id)
        return nodes, edges


class JavaScriptParser(LanguageParser):
    """Parser for JavaScript and JSX files."""

    def __init__(self):
        super().__init__("javascript")

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        file_name = file_path.split("/")[-1]
        file_module_id = self._get_id(file_path, file_name)
        nodes.append(
            self._create_node(file_module_id, file_name, "module", file_path, tree.root_node)
        )

        def traverse(node: Node, parent_id: str | None = None):
            node_id = None

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

                nodes.append(self._create_node(node_id, name, kind, file_path, node, signature))

                if parent_id:
                    edges.append(self._create_edge(parent_id, node_id))

            # Class declarations
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)

                    nodes.append(self._create_node(node_id, name, "class", file_path, node))

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
                traverse(child, current_scope_id)

        traverse(tree.root_node, file_module_id)
        return nodes, edges


class TypeScriptParser(LanguageParser):
    """Parser for TypeScript and TSX files."""

    def __init__(self, language="typescript"):
        super().__init__(language)

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        file_name = file_path.split("/")[-1]
        file_module_id = self._get_id(file_path, file_name)
        nodes.append(
            self._create_node(file_module_id, file_name, "module", file_path, tree.root_node)
        )

        def traverse(node: Node, parent_id: str | None = None):
            node_id = None

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

                nodes.append(self._create_node(node_id, name, kind, file_path, node, signature))

                if parent_id:
                    edges.append(self._create_edge(parent_id, node_id))

            # Class, interface declarations
            elif node.type in ("class_declaration", "interface_declaration"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)
                    kind = "interface" if node.type == "interface_declaration" else "class"

                    nodes.append(self._create_node(node_id, name, kind, file_path, node))

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

    def __init__(self):
        super().__init__("go")

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        file_name = file_path.split("/")[-1]
        file_module_id = self._get_id(file_path, file_name)
        nodes.append(
            self._create_node(file_module_id, file_name, "module", file_path, tree.root_node)
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

    def __init__(self):
        super().__init__("rust")

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        file_name = file_path.split("/")[-1]
        file_module_id = self._get_id(file_path, file_name)
        nodes.append(
            self._create_node(file_module_id, file_name, "module", file_path, tree.root_node)
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

    def __init__(self, language: str):
        super().__init__(language)
        self.language_name = language

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        if not source_code.strip():
            return [], []

        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Create a node for the file itself (module)
        file_name = file_path.split("/")[-1]
        file_module_id = self._get_id(file_path, file_name)
        nodes.append(
            self._create_node(file_module_id, file_name, "module", file_path, tree.root_node)
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
    def get_parser(file_path: str) -> LanguageParser | None:
        if file_path.endswith(".py"):
            return PythonParser()
        elif file_path.endswith((".js", ".jsx")):
            return JavaScriptParser()
        elif file_path.endswith(".ts"):
            return TypeScriptParser("typescript")
        elif file_path.endswith(".tsx"):
            return TypeScriptParser("tsx")
        elif file_path.endswith(".go"):
            return GoParser()
        elif file_path.endswith(".rs"):
            return RustParser()
        elif file_path.endswith(".java"):
            return GenericParser("java")
        elif file_path.endswith((".c", ".h")):
            return GenericParser("c")
        elif file_path.endswith((".cpp", ".cc", ".cxx", ".hpp")):
            return GenericParser("cpp")
        elif file_path.endswith(".cs"):
            return GenericParser("c_sharp")
        elif file_path.endswith(".rb"):
            return GenericParser("ruby")
        elif file_path.endswith(".php"):
            return GenericParser("php")
        return None
