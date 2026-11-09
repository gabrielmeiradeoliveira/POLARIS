"""Tests for Incremental Analysis Engine (GOAL 30 - Fase 30.3)."""

from polaris.context.incremental_engine import FileChangeKind, IncrementalAnalysisEngine
from polaris.context.semantic_graph import EdgeKind, EntityKind, GraphEdge, GraphEntity, SemanticProjectGraph


def test_incremental_change_detection():
    """Verify detection of added, modified, unchanged, and deleted files."""
    engine = IncrementalAnalysisEngine()
    engine.sync_file("app.py", "def main(): pass", [], [])

    changes = engine.detect_changes({
        "app.py": "def main(): return 1",  # modified
        "new.py": "x = 1",                  # added
    })

    assert changes["app.py"] == FileChangeKind.MODIFIED
    assert changes["new.py"] == FileChangeKind.ADDED

    # Deleted file detection
    changes2 = engine.detect_changes({})
    assert changes2["app.py"] == FileChangeKind.DELETED


def test_incremental_invalidation_cleanly_removes_edges():
    """Verify that updating a file removes obsolete entities and edges without ghost references."""
    graph = SemanticProjectGraph()
    engine = IncrementalAnalysisEngine(graph)

    e1 = GraphEntity(id="e1", kind=EntityKind.FUNCTION, name="fn1", file_path="a.py")
    e2 = GraphEntity(id="e2", kind=EntityKind.FUNCTION, name="fn2", file_path="b.py")
    edge = GraphEdge(source_id="e1", target_id="e2", kind=EdgeKind.CALLS)

    engine.sync_file("a.py", "def fn1(): fn2()", [e1], [edge])
    engine.sync_file("b.py", "def fn2(): pass", [e2], [])

    assert len(graph.entities) == 2
    assert len(graph.edges) == 1

    # Invalidate a.py
    engine.invalidate_file("a.py")
    assert "e1" not in graph.entities
    assert len(graph.edges) == 0  # Edge referencing e1 removed
