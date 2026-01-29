from vibegraph.indexer.parser import PythonParser


def test_python_extraction():
    parser = PythonParser()
    source_code = b"""
def hello_world(name):
    \"\"\"This is a docstring.\"\"\"
    print(name)

class MyClass:
    def method(self):
        pass
"""
    file_path = "/tmp/test.py"
    nodes, edges = parser.extract(file_path, source_code)

    # Check Nodes
    assert len(nodes) == 3

    # Node 1: hello_world
    func_node = next(n for n in nodes if n.name == "hello_world")
    assert func_node.kind == "function"
    assert func_node.docstring == "This is a docstring."
    assert "(name)" in func_node.signature

    # Node 2: MyClass
    class_node = next(n for n in nodes if n.name == "MyClass")
    assert class_node.kind == "class"

    # Node 3: method
    method_node = next(n for n in nodes if n.name == "method")
    assert method_node.kind == "function"

    # Check Edges (MyClass defines method)
    assert len(edges) == 1
    edge = edges[0]
    assert edge.from_node_id == class_node.id
    assert edge.to_node_id == method_node.id
    assert edge.relation_type == "defines"
