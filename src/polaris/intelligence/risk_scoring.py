"""Explainable Risk Scoring Engine (GOAL 30 - Fase 30.11).

Produces reproducible, deterministic risk scores and factor breakdowns
based on severity, confidence, architectural exposure, and evidence.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskBreakdown(BaseModel):
    """Auditable component breakdown of a risk score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_severity_score: float
    confidence_weight: float
    architectural_exposure_multiplier: float
    final_score: float
    risk_level: str
    explanation: str


class ExplainableRiskScoring:
    """Calculates deterministic risk scores for code findings and diffs."""

    SEVERITY_WEIGHTS = {
        "CRITICAL": 100.0,
        "HIGH": 75.0,
        "MEDIUM": 40.0,
        "LOW": 15.0,
        "INFO": 5.0,
    }

    CONFIDENCE_WEIGHTS = {
        "CONFIRMED": 1.0,
        "HIGH": 0.9,
        "MEDIUM": 0.7,
        "SUSPECTED": 0.5,
        "LOW": 0.3,
    }

    @classmethod
    def calculate_finding_risk(
        cls,
        severity: str,
        confidence: str,
        impact_scope: str = "DIRECT",
    ) -> RiskBreakdown:
        """Calculate finding risk with transparent factor decomposition."""
        base = cls.SEVERITY_WEIGHTS.get(severity.upper(), 20.0)
        conf_w = cls.CONFIDENCE_WEIGHTS.get(confidence.upper(), 0.5)

        # Exposure multiplier based on dependency reach
        if impact_scope.upper() in ("DIRECT", "TRANSITIVE"):
            mult = 1.2
        elif impact_scope.upper() == "LOCAL":
            mult = 1.0
        else:
            mult = 0.8

        final = round(base * conf_w * mult, 2)

        if final >= 70.0:
            level = "CRITICAL"
        elif final >= 45.0:
            level = "HIGH"
        elif final >= 20.0:
            level = "MEDIUM"
        else:
            level = "LOW"

        explanation = (
            f"Risk score {final} ({level}) calculated from base severity '{severity}' ({base}), "
            f"confidence '{confidence}' ({conf_w}), and exposure multiplier ({mult})."
        )

        return RiskBreakdown(
            base_severity_score=base,
            confidence_weight=conf_w,
            architectural_exposure_multiplier=mult,
            final_score=final,
            risk_level=level,
            explanation=explanation,
        )
