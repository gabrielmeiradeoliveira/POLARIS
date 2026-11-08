"""Evidence Fusion Engine (GOAL 30 - Fase 30.10).

Integrates multi-source evidence from AST, Semantic Graph, Dataflow,
Security Guardrails, and Contracts into unified, deduplicated findings.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class EvidenceSource(StrEnum):
    """Source subsystem originating the evidence."""

    SECURITY_GUARDRAIL = "SECURITY_GUARDRAIL"
    CONTRACT_ENGINE = "CONTRACT_ENGINE"
    DATAFLOW_ENGINE = "DATAFLOW_ENGINE"
    BEHAVIORAL_DELTA = "BEHAVIORAL_DELTA"
    LLM_REVIEW = "LLM_REVIEW"


class FusedEvidence(BaseModel):
    """Unified evidence piece with stable SHA-256 identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    source: EvidenceSource
    file_path: str
    line: int
    rule_or_category: str
    description: str
    confidence: str = "CONFIRMED"

    @classmethod
    def create(
        cls,
        source: EvidenceSource,
        file_path: str,
        line: int,
        rule_or_category: str,
        description: str,
        confidence: str = "CONFIRMED",
    ) -> FusedEvidence:
        """Construct deterministic SHA-256 evidence identity."""
        norm_p = file_path.replace("\\", "/")
        seed = f"{source.value}::{norm_p}::{line}::{rule_or_category}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        ev_id = f"ev:{digest}"
        return cls(
            evidence_id=ev_id,
            source=source,
            file_path=norm_p,
            line=line,
            rule_or_category=rule_or_category,
            description=description,
            confidence=confidence,
        )


class EvidenceFusionEngine:
    """Fuses and deduplicates evidences from multiple analysis modules."""

    @classmethod
    def fuse_evidences(cls, evidences: list[FusedEvidence]) -> list[FusedEvidence]:
        """Deduplicate evidences deterministically by stable ID."""
        by_id: dict[str, FusedEvidence] = {}
        for ev in sorted(evidences, key=lambda x: (x.file_path, x.line, x.source.value)):
            if ev.evidence_id not in by_id:
                by_id[ev.evidence_id] = ev
        return list(by_id.values())
