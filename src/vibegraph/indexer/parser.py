import hashlib
from abc import ABC, abstractmethod
from typing import Optional

from tree_sitter import Language, Node, Parser, Tree
from tree_sitter_languages import get_language, get_parser

from vibegraph.indexer.db import Edge, Node as DBNode


class LanguageParser(ABC):
    def __init__(self, language_name: str):
        self.language: Language = get_language(language_name)
        self.parser: Parser = get_parser(language_name)

    def parse(self, source_code: bytes) -> Tree:
        return self.parser.parse(source_code)

    @abstractmethod
    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        """Extract nodes and edges from source code."""
        pass


class PythonParser(LanguageParser):
    def __init__(self):
        super().__init__("python")

    def _get_text(self, node: Node) -> str:
        return node.text.decode("utf-8")

    def _get_id(self, file_path: str, name: str) -> str:
        return hashlib.md5(f"{file_path}::{name}".encode()).hexdigest()

    def _extract_docstring(self, node: Node) -> Optional[str]:
        body_node = node.child_by_field_name("body")
        if not body_node:
            return None
        
        for child in body_node.children:
            if child.type == "expression_statement":
                first_child = child.children[0]
                if first_child.type == "string":
                    return self._get_text(first_child).strip('"""').strip("'''")
            elif child.type == "comment":
                continue
            else:
                break
        return None

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        def traverse(node: Node, parent_id: Optional[str] = None):
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

                    nodes.append(DBNode(
                        id=node_id,
                        name=name,
                        kind=kind,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=signature,
                        docstring=docstring,
                    ))

                    if parent_id:
                        edges.append(Edge(
                            from_node_id=parent_id,
                            to_node_id=node_id,
                            relation_type="defines"
                        ))

            # 2. Calls (simplified for now, avoiding unused variable lint)
            elif node.type == "call":
                # func_node = node.child_by_field_name("function")
                # if func_node and parent_id:
                #    pass # Logic for call edges would go here
                pass

            # Recurse
            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node)
        return nodes, edges

class JavaScriptParser(LanguageParser):
    """Parser for JavaScript and JSX files."""
    def __init__(self):
        super().__init__("javascript")

    def _get_text(self, node: Node) -> str:
        return node.text.decode("utf-8")

    def _get_id(self, file_path: str, name: str) -> str:
        return hashlib.md5(f"{file_path}::{name}".encode()).hexdigest()

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        def traverse(node: Node, parent_id: Optional[str] = None):
            node_id = None

            # Function declarations, arrow functions, class methods
            if node.type in ("function_declaration", "arrow_function", "function", "method_definition"):
                name_node = node.child_by_field_name("name")
                name = self._get_text(name_node) if name_node else "<anonymous>"
                
                node_id = self._get_id(file_path, name)
                kind = "function"
                
                params_node = node.child_by_field_name("parameters")
                signature = self._get_text(params_node) if params_node else None

                nodes.append(DBNode(
                    id=node_id,
                    name=name,
                    kind=kind,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=signature,
                    docstring=None,
                ))

                if parent_id:
                    edges.append(Edge(
                        from_node_id=parent_id,
                        to_node_id=node_id,
                        relation_type="defines"
                    ))

            # Class declarations
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)

                    nodes.append(DBNode(
                        id=node_id,
                        name=name,
                        kind="class",
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=None,
                        docstring=None,
                    ))

                    if parent_id:
                        edges.append(Edge(
                            from_node_id=parent_id,
                            to_node_id=node_id,
                            relation_type="defines"
                        ))

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node)
        return nodes, edges


class TypeScriptParser(LanguageParser):
    """Parser for TypeScript and TSX files."""
    def __init__(self, language="typescript"):
        super().__init__(language)

    def _get_text(self, node: Node) -> str:
        return node.text.decode("utf-8")

    def _get_id(self, file_path: str, name: str) -> str:
        return hashlib.md5(f"{file_path}::{name}".encode()).hexdigest()

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        def traverse(node: Node, parent_id: Optional[str] = None):
            node_id = None

            # Function declarations, arrow functions, methods
            if node.type in ("function_declaration", "arrow_function", "function", "method_definition", "method_signature"):
                name_node = node.child_by_field_name("name")
                name = self._get_text(name_node) if name_node else "<anonymous>"
                
                node_id = self._get_id(file_path, name)
                kind = "function"
                
                params_node = node.child_by_field_name("parameters")
                signature = self._get_text(params_node) if params_node else None

                nodes.append(DBNode(
                    id=node_id,
                    name=name,
                    kind=kind,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=signature,
                    docstring=None,
                ))

                if parent_id:
                    edges.append(Edge(
                        from_node_id=parent_id,
                        to_node_id=node_id,
                        relation_type="defines"
                    ))

            # Class, interface declarations
            elif node.type in ("class_declaration", "interface_declaration"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)
                    kind = "interface" if node.type == "interface_declaration" else "class"

                    nodes.append(DBNode(
                        id=node_id,
                        name=name,
                        kind=kind,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=None,
                        docstring=None,
                    ))

                    if parent_id:
                        edges.append(Edge(
                            from_node_id=parent_id,
                            to_node_id=node_id,
                            relation_type="defines"
                        ))

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node)
        return nodes, edges


class GoParser(LanguageParser):
    """Parser for Go files."""
    def __init__(self):
        super().__init__("go")

    def _get_text(self, node: Node) -> str:
        return node.text.decode("utf-8")

    def _get_id(self, file_path: str, name: str) -> str:
        return hashlib.md5(f"{file_path}::{name}".encode()).hexdigest()

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        def traverse(node: Node, parent_id: Optional[str] = None):
            node_id = None

            # Function declarations, methods
            if node.type in ("function_declaration", "method_declaration"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)
                    
                    params_node = node.child_by_field_name("parameters")
                    signature = self._get_text(params_node) if params_node else None

                    nodes.append(DBNode(
                        id=node_id,
                        name=name,
                        kind="function",
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=signature,
                        docstring=None,
                    ))

                    if parent_id:
                        edges.append(Edge(
                            from_node_id=parent_id,
                            to_node_id=node_id,
                            relation_type="defines"
                        ))

            # Type declarations (struct, interface)
            elif node.type == "type_declaration":
                type_spec = node.child_by_field_name("type")
                if type_spec:
                    name_node = type_spec.child_by_field_name("name")
                    if name_node:
                        name = self._get_text(name_node)
                        node_id = self._get_id(file_path, name)
                        kind = "interface" if type_spec.type == "interface_type" else "class"

                        nodes.append(DBNode(
                            id=node_id,
                            name=name,
                            kind=kind,
                            file_path=file_path,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            signature=None,
                            docstring=None,
                        ))

                        if parent_id:
                            edges.append(Edge(
                                from_node_id=parent_id,
                                to_node_id=node_id,
                                relation_type="defines"
                            ))

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node)
        return nodes, edges


class RustParser(LanguageParser):
    """Parser for Rust files."""
    def __init__(self):
        super().__init__("rust")

    def _get_text(self, node: Node) -> str:
        return node.text.decode("utf-8")

    def _get_id(self, file_path: str, name: str) -> str:
        return hashlib.md5(f"{file_path}::{name}".encode()).hexdigest()

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        def traverse(node: Node, parent_id: Optional[str] = None):
            node_id = None

            # Function items
            if node.type == "function_item":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)
                    
                    params_node = node.child_by_field_name("parameters")
                    signature = self._get_text(params_node) if params_node else None

                    nodes.append(DBNode(
                        id=node_id,
                        name=name,
                        kind="function",
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=signature,
                        docstring=None,
                    ))

                    if parent_id:
                        edges.append(Edge(
                            from_node_id=parent_id,
                            to_node_id=node_id,
                            relation_type="defines"
                        ))

            # Struct, trait, impl declarations
            elif node.type in ("struct_item", "trait_item", "impl_item"):
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)
                    kind = "interface" if node.type == "trait_item" else "class"

                    nodes.append(DBNode(
                        id=node_id,
                        name=name,
                        kind=kind,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=None,
                        docstring=None,
                    ))

                    if parent_id:
                        edges.append(Edge(
                            from_node_id=parent_id,
                            to_node_id=node_id,
                            relation_type="defines"
                        ))

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node)
        return nodes, edges


class GenericParser(LanguageParser):
    """Generic parser for languages with basic function/class extraction."""
    def __init__(self, language: str):
        super().__init__(language)
        self.language_name = language

    def _get_text(self, node: Node) -> str:
        return node.text.decode("utf-8")

    def _get_id(self, file_path: str, name: str) -> str:
        return hashlib.md5(f"{file_path}::{name}".encode()).hexdigest()

    def extract(self, file_path: str, source_code: bytes) -> tuple[list[DBNode], list[Edge]]:
        tree = self.parse(source_code)
        nodes: list[DBNode] = []
        edges: list[Edge] = []

        # Common node types across C-like languages
        function_types = {
            "function_definition", "function_declaration", "method_declaration",
            "function_item", "method_definition"
        }
        class_types = {
            "class_definition", "class_declaration", "struct_declaration",
            "interface_declaration", "trait_item"
        }

        def traverse(node: Node, parent_id: Optional[str] = None):
            node_id = None

            if node.type in function_types:
                name_node = node.child_by_field_name("name") or node.child_by_field_name("declarator")
                if name_node:
                    # For C/C++, might need to extract from declarator
                    name_text = self._get_text(name_node)
                    # Simple extraction - get first identifier
                    name = name_text.split("(")[0].strip().split()[-1] if "(" in name_text else name_text
                    
                    node_id = self._get_id(file_path, name)

                    nodes.append(DBNode(
                        id=node_id,
                        name=name,
                        kind="function",
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=None,
                        docstring=None,
                    ))

                    if parent_id:
                        edges.append(Edge(
                            from_node_id=parent_id,
                            to_node_id=node_id,
                            relation_type="defines"
                        ))

            elif node.type in class_types:
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._get_text(name_node)
                    node_id = self._get_id(file_path, name)

                    nodes.append(DBNode(
                        id=node_id,
                        name=name,
                        kind="class",
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        signature=None,
                        docstring=None,
                    ))

                    if parent_id:
                        edges.append(Edge(
                            from_node_id=parent_id,
                            to_node_id=node_id,
                            relation_type="defines"
                        ))

            current_scope_id = node_id if node_id else parent_id
            for child in node.children:
                traverse(child, current_scope_id)

        traverse(tree.root_node)
        return nodes, edges


class ParserFactory:
    @staticmethod
    def get_parser(file_path: str) -> Optional[LanguageParser]:
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
