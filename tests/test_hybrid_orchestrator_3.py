"""Tests for Hybrid Orchestrator 3.0 (GOAL 30 - Fase 30.12)."""

from polaris.core.models import BudgetTracker, ExecutionBudget
from tests.test_hybrid_orchestrator import ScriptedProvider
from polaris.review.orchestrator_3 import HybridOrchestrator3


def test_hybrid_orchestrator_3_end_to_end():
    """Verify deep review pipeline executes and fuses static findings with dataflow and risk scoring."""
    orchestrator = HybridOrchestrator3()
    provider = ScriptedProvider()
    tracker = BudgetTracker(ExecutionBudget(max_total_tokens=10_000, max_requests=10))

    changed_code = """
def search(request):
    raw_q = request.args['q']
    cursor.execute(f"SELECT * FROM items WHERE name = {raw_q}")
"""

    res = orchestrator.run_deep_review(
        changed_file="views/search.py",
        before_content="def search(request): pass",
        after_content=changed_code,
        diff_text="+ cursor.execute",
        provider=provider,
        tracker=tracker,
    )

    assert res["dataflow_count"] >= 1
    assert len(res["fused_evidences"]) >= 1
    assert len(res["risk_scores"]) >= 1
    first_ev = res["fused_evidences"][0]
    assert first_ev["evidence_id"].startswith("ev:")
    assert first_ev["evidence_id"] in res["risk_scores"]
