"""Tests for Interprocedural Impact Analysis (GOAL 30 - Fase 30.4)."""

from polaris.context.impact_analysis import ImpactClassification, InterproceduralImpactAnalysis
from polaris.context.semantic_graph import EdgeKind, EntityKind, GraphEdge, GraphEntity, SemanticProjectGraph


def test_interprocedural_direct_and_transitive_impact():
    """Verify that upstream changes accurately resolve direct callers and transitive consumers."""
    graph = SemanticProjectGraph()

    # Leaf service
    e_leaf = GraphEntity(id="fn_db_query", kind=EntityKind.FUNCTION, name="db_query", file_path="db.py")
    # Direct caller
    e_mid = GraphEntity(id="fn_get_user", kind=EntityKind.FUNCTION, name="get_user", file_path="user_service.py")
    # Transitive caller
    e_top = GraphEntity(id="fn_render_profile", kind=EntityKind.FUNCTION, name="render_profile", file_path="views.py")

    for e in (e_leaf, e_mid, e_top):
        graph.add_entity(e)

    # user_service CALLS db_query
    graph.add_edge(GraphEdge(source_id="fn_get_user", target_id="fn_db_query", kind=EdgeKind.CALLS))
    # views CALLS user_service
    graph.add_edge(GraphEdge(source_id="fn_render_profile", target_id="fn_get_user", kind=EdgeKind.CALLS))

    analyzer = InterproceduralImpactAnalysis(graph)
    impacted = analyzer.analyze_impact(["fn_db_query"])

    assert len(impacted) == 2
    by_id = {item.consumer_id: item for item in impacted}

    assert by_id["fn_get_user"].classification == ImpactClassification.DIRECT
    assert by_id["fn_render_profile"].classification == ImpactClassification.TRANSITIVE
