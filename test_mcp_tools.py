import asyncio
import sys
from pathlib import Path

# Add src to sys.path
sys.path.append("src")

from vibegraph.mcp.server import (
    vibegraph_get_structural_summary,
    vibegraph_get_call_stack,
    vibegraph_impact_analysis,
    vibegraph_find_references,
    vibegraph_get_dependencies,
    vibegraph_search_by_signature,
    StructuralSummaryInput,
    CallStackInput,
    ImpactAnalysisInput,
    ReferencesInput,
    DependenciesInput,
    SearchInput,
    ResponseFormat,
)


async def test_tools():
    print("=== Testing MCP Tools ===")

    # 1. Structural Summary
    print("\n--- vibegraph_get_structural_summary ---")
    try:
        res = await vibegraph_get_structural_summary(
            StructuralSummaryInput(file_path="src/vibegraph/indexer/db.py")
        )
        print(res[:500] + "..." if len(res) > 500 else res)
    except Exception as e:
        print(f"FAILED: {e}")

    # 2. Call Stack
    print("\n--- vibegraph_get_call_stack ---")
    try:
        # Check what calls 'upsert_node'
        res = await vibegraph_get_call_stack(
            CallStackInput(node_name="upsert_node", direction="up")
        )
        print(res[:500] + "..." if len(res) > 500 else res)
    except Exception as e:
        print(f"FAILED: {e}")

    # 3. Impact Analysis
    print("\n--- vibegraph_impact_analysis ---")
    try:
        res = await vibegraph_impact_analysis(
            ImpactAnalysisInput(file_path="src/vibegraph/indexer/db.py")
        )
        print(res[:500] + "..." if len(res) > 500 else res)
    except Exception as e:
        print(f"FAILED: {e}")

    # 4. Find References
    print("\n--- vibegraph_find_references ---")
    try:
        res = await vibegraph_find_references(ReferencesInput(symbol_name="IndexerDB"))
        print(res[:500] + "..." if len(res) > 500 else res)
    except Exception as e:
        print(f"FAILED: {e}")

    # 5. Dependencies
    print("\n--- vibegraph_get_dependencies ---")
    try:
        res = await vibegraph_get_dependencies(
            DependenciesInput(file_path="src/vibegraph/indexer/main.py")
        )
        print(res[:500] + "..." if len(res) > 500 else res)
    except Exception as e:
        print(f"FAILED: {e}")

    # 6. Search by Signature
    print("\n--- vibegraph_search_by_signature ---")
    try:
        res = await vibegraph_search_by_signature(SearchInput(pattern="%IndexerDB%"))
        print(res[:500] + "..." if len(res) > 500 else res)
    except Exception as e:
        print(f"FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(test_tools())
