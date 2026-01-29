from vibegraph.indexer.parser import JavaScriptParser, TypeScriptParser, GoParser, RustParser

# Test JavaScript
js_code = b"""
class Calculator {
    add(a, b) {
        return a + b;
    }
}

function multiply(x, y) {
    return x * y;
}

const divide = (a, b) => a / b;
"""

js_parser = JavaScriptParser()
js_nodes, js_edges = js_parser.extract("test.js", js_code)
print("JavaScript Extraction:")
print(f"  Nodes: {len(js_nodes)}")
for node in js_nodes:
    print(f"    - {node.kind}: {node.name} (L{node.start_line}-{node.end_line})")
print(f"  Edges: {len(js_edges)}")
print()

# Test TypeScript
ts_code = b"""
interface User {
    name: string;
    age: number;
}

class UserService {
    getUser(id: number): User {
        return { name: "Test", age: 25 };
    }
}

function processUser(user: User): void {
    console.log(user.name);
}
"""

ts_parser = TypeScriptParser()
ts_nodes, ts_edges = ts_parser.extract("test.ts", ts_code)
print("TypeScript Extraction:")
print(f"  Nodes: {len(ts_nodes)}")
for node in ts_nodes:
    print(f"    - {node.kind}: {node.name} (L{node.start_line}-{node.end_line})")
print(f"  Edges: {len(ts_edges)}")
print()

# Test Go
go_code = b"""
package main

type Person struct {
    Name string
    Age  int
}

func (p *Person) Greet() string {
    return "Hello, " + p.Name
}

func main() {
    println("Hello, World!")
}
"""

go_parser = GoParser()
go_nodes, go_edges = go_parser.extract("test.go", go_code)
print("Go Extraction:")
print(f"  Nodes: {len(go_nodes)}")
for node in go_nodes:
    print(f"    - {node.kind}: {node.name} (L{node.start_line}-{node.end_line})")
print(f"  Edges: {len(go_edges)}")
print()

# Test Rust
rust_code = b"""
struct Point {
    x: i32,
    y: i32,
}

impl Point {
    fn new(x: i32, y: i32) -> Point {
        Point { x, y }
    }
}

fn distance(p1: &Point, p2: &Point) -> f64 {
    let dx = (p2.x - p1.x) as f64;
    let dy = (p2.y - p1.y) as f64;
    (dx * dx + dy * dy).sqrt()
}
"""

rust_parser = RustParser()
rust_nodes, rust_edges = rust_parser.extract("test.rs", rust_code)
print("Rust Extraction:")
print(f"  Nodes: {len(rust_nodes)}")
for node in rust_nodes:
    print(f"    - {node.kind}: {node.name} (L{node.start_line}-{node.end_line})")
print(f"  Edges: {len(rust_edges)}")
