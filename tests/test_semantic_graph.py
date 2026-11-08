"""Tests for Semantic Project Graph (GOAL 30 - Fase 30.2)."""

import json
from pathlib import Path

from polaris.context.semantic_graph import (
    EdgeCertainty,
    EdgeKind,
    EntityKind,
    GraphEdge,
    GraphEntity,
    SemanticProjectGraph,
)


def test_entity_creation_deterministic_ids():
    """Verify deterministic ID creation regardless of invocation order."""
    id1 = GraphEntity.create_id(EntityKind.FUNCTION, "pkg/utils.py", "calculate_tax", 10)
    id2 = GraphEntity.create_id(EntityKind.FUNCTION, "pkg/utils.py", "calculate_tax", 10)
    id3 = GraphEntity.create_id(EntityKind.FUNCTION, "pkg/utils.py", "calculate_tax", 20)

    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("function:")


def test_semantic_graph_cycle_detection():
    """Verify cycle detection across inter-dependent entities."""
    graph = SemanticProjectGraph()

    e1 = GraphEntity(id="mod_a", kind=EntityKind.MODULE, name="mod_a", file_path="mod_a.py")
    e2 = GraphEntity(id="mod_b", kind=EntityKind.MODULE, name="mod_b", file_path="mod_b.py")
    e3 = GraphEntity(id="mod_c", kind=EntityKind.MODULE, name="mod_c", file_path="mod_c.py")

    for e in (e1, e2, e3):
        graph.add_entity(e)

    graph.add_edge(GraphEdge(source_id="mod_a", target_id="mod_b", kind=EdgeKind.IMPORTS))
    graph.add_edge(GraphEdge(source_id="mod_b", target_id="mod_c", kind=EdgeKind.CALLS))
    graph.add_edge(GraphEdge(source_id="mod_c", target_id="mod_a", kind=EdgeKind.DEPENDS_ON))

    cycles = graph.detect_cycles()
    assert len(cycles) > 0
    cycle_nodes = set(cycles[0])
    assert {"mod_a", "mod_b", "mod_c"}.issubset(cycle_nodes)


def test_semantic_graph_atomic_persistence_and_corrupt_recovery(tmp_path: Path):
    """Verify persistence, serialization, and recovery from corrupted data."""
    graph = SemanticProjectGraph(repo_root=tmp_path)
    e = GraphEntity(id="fn_1", kind=EntityKind.FUNCTION, name="process", file_path="core.py", start_line=5, end_line=15)
    graph.add_entity(e)

    save_path = tmp_path / "graph.json"
    graph.save(save_path)
    assert save_path.exists()

    # Successful reload
    loaded = SemanticProjectGraph.load(save_path, repo_root=tmp_path)
    assert loaded.get_entity("fn_1") is not None
    assert loaded.get_entity("fn_1").name == "process"

    # Corrupt file test
    save_path.write_text("{invalid json", encoding="utf-8")
    recovered = SemanticProjectGraph.load(save_path, repo_root=tmp_path)
    assert len(recovered.entities) == 0  # Recovered cleanly to empty graph
