"""Tests for Evidence Fusion Engine (GOAL 30 - Fase 30.10)."""

from polaris.arbitration.evidence_fusion import EvidenceFusionEngine, EvidenceSource, FusedEvidence


def test_evidence_fusion_deterministic_deduplication():
    """Verify that multiple matching evidence artifacts resolve into a stable unified ID."""
    ev1 = FusedEvidence.create(
        source=EvidenceSource.SECURITY_GUARDRAIL,
        file_path="auth/views.py",
        line=42,
        rule_or_category="SEC-AUTH-002",
        description="Unconditional bypass",
    )
    ev2 = FusedEvidence.create(
        source=EvidenceSource.SECURITY_GUARDRAIL,
        file_path="auth/views.py",
        line=42,
        rule_or_category="SEC-AUTH-002",
        description="Unconditional bypass duplicate report",
    )

    fused = EvidenceFusionEngine.fuse_evidences([ev1, ev2])
    assert len(fused) == 1
    assert fused[0].evidence_id == ev1.evidence_id
    assert fused[0].evidence_id.startswith("ev:")
