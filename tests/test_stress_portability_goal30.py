"""Tests for Stress, Resilience, and Portability (GOAL 30 - Fase 30.15)."""

import time
from polaris.context.semantic_graph import EdgeKind, EntityKind, GraphEdge, GraphEntity, SemanticProjectGraph


def test_stress_graph_with_high_fanout_and_depth():
    """Verify semantic graph performance with 500 nodes and high fan-out."""
    start_time = time.perf_counter()
    graph = SemanticProjectGraph()

    # Create root
    root = GraphEntity(id="root", kind=EntityKind.MODULE, name="root", file_path="root.py")
    graph.add_entity(root)

    # Add 500 dependent entities
    for i in range(500):
        ent = GraphEntity(id=f"node_{i}", kind=EntityKind.FUNCTION, name=f"fn_{i}", file_path=f"pkg/sub_{i}.py")
        graph.add_entity(ent)
        graph.add_edge(GraphEdge(source_id="root", target_id=f"node_{i}", kind=EdgeKind.CALLS))

    elapsed = time.perf_counter() - start_time
    assert len(graph.entities) == 501
    assert len(graph.edges) == 500
    assert elapsed < 1.0  # Must construct within 1 second


def test_portability_unicode_and_spaced_file_paths():
    """Verify correct graph normalization and ID stability for paths with spaces and Unicode."""
    graph = SemanticProjectGraph()
    path = "serviços de cobrança/faturamento usuário.py"
    ent = GraphEntity(
        id=GraphEntity.create_id(EntityKind.FUNCTION, path, "calcular_tarifa"),
        kind=EntityKind.FUNCTION,
        name="calcular_tarifa",
        file_path=path,
    )
    graph.add_entity(ent)

    assert ent.id.startswith("function:")
    assert graph.get_entity(ent.id) is not None
    assert graph.get_entity(ent.id).file_path == path
