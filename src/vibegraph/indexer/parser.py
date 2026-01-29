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

class ParserFactory:
    @staticmethod
    def get_parser(file_path: str) -> Optional[LanguageParser]:
        if file_path.endswith(".py"):
            return PythonParser()
        return None
