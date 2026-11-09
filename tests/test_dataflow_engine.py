"""Tests for Dataflow Analysis Engine (GOAL 30 - Fase 30.5)."""

from polaris.context.dataflow_engine import DataflowAnalysisEngine, TaintStatus


def test_dataflow_proven_taint_propagation():
    """Verify end-to-end taint detection from untrusted source to sink."""
    code = """
def handle_request(request):
    raw_id = request.args['id']
    query = f"SELECT * FROM users WHERE id = {raw_id}"
    cursor.execute(query)
"""
    engine = DataflowAnalysisEngine()
    flows = engine.analyze_source(code)

    assert len(flows) >= 1
    flow = flows[0]
    assert flow.status == TaintStatus.PROVEN
    assert "cursor.execute" in flow.sink
    assert "request.args" in flow.source


def test_dataflow_sanitized_flow_prevents_false_alarm():
    """Verify that recognized sanitization functions suppress false alarms."""
    code = """
def handle_request(request):
    raw_id = int(request.args['id'])
    query = f"SELECT * FROM users WHERE id = {raw_id}"
    cursor.execute(query)
"""
    engine = DataflowAnalysisEngine()
    flows = engine.analyze_source(code)

    assert len(flows) == 0
