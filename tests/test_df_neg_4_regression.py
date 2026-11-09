"""Regression test documenting known false positive scenario df_neg_4."""

from polaris.context.dataflow_engine import DataflowAnalysisEngine, TaintStatus


def test_dataflow_known_limitation_parameterized_query_tuple():
    """Documents limitation: syntax-level call check currently triggers on execute() arguments

    even when parameterized in a tuple, until semantic tuple binding analysis is added.
    """
    code = "def f(request):\n  cursor.execute('SELECT * FROM t WHERE id = %s', (request.args['id'],))\n"
    engine = DataflowAnalysisEngine()
    flows = engine.analyze_source(code)

    # Documented behavior: currently flags because request.args is in arguments of cursor.execute
    assert len(flows) >= 1
    assert flows[0].status == TaintStatus.PROVEN
    assert "cursor.execute" in flows[0].sink
