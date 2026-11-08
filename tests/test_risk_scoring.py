"""Tests for Explainable Risk Scoring Engine (GOAL 30 - Fase 30.11)."""

from polaris.intelligence.risk_scoring import ExplainableRiskScoring


def test_explainable_risk_scoring_deterministic():
    """Verify reproducible calculation and transparent component explanation."""
    breakdown = ExplainableRiskScoring.calculate_finding_risk(
        severity="HIGH",
        confidence="CONFIRMED",
        impact_scope="DIRECT",
    )

    # 75.0 * 1.0 * 1.2 = 90.0
    assert breakdown.final_score == 90.0
    assert breakdown.risk_level == "CRITICAL"
    assert "Risk score 90.0 (CRITICAL)" in breakdown.explanation
    assert breakdown.base_severity_score == 75.0
    assert breakdown.confidence_weight == 1.0
    assert breakdown.architectural_exposure_multiplier == 1.2
