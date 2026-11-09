"""Structured immutable Evidence Registry for POLARIS Finding Arbitration (GOAL 28.4)."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polaris.core.models import LineRange
from polaris.guardrails.models import GuardrailConfidence


class EvidenceSource(StrEnum):
    """Origin source of an evidence record."""

    STATIC_SECURITY = "static_security"
    STATIC_CONTRACT = "static_contract"
    OFF_DIFF_ONLY = "off_diff_only"
    ON_BEHAVIORAL_DELTA = "on_behavioral_delta"


class EvidenceRecord(BaseModel):
    """Structured, immutable evidence entry with a deterministic ID."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(..., description="Deterministic hash of the semantic content.")
    source: EvidenceSource = Field(...)
    file_path: str = Field(...)
    line_range: LineRange = Field(...)
    symbol: str | None = Field(default=None)
    property_or_contract: str = Field(...)
    confidence: GuardrailConfidence = Field(...)
    description: str = Field(...)
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        source: EvidenceSource,
        file_path: str,
        line_range: LineRange,
        property_or_contract: str,
        confidence: GuardrailConfidence,
        description: str,
        symbol: str | None = None,
        limitations: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceRecord:
        """Construct an EvidenceRecord computing an order-independent deterministic ID."""
        norm_path = file_path.replace("\\", "/")
        payload = {
            "source": source.value,
            "file": norm_path,
            "start": line_range.start_line,
            "end": line_range.end_line,
            "sym": symbol or "",
            "prop": property_or_contract,
            "conf": confidence.value,
            "desc": description.strip(),
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        evidence_id = f"ev-{hashlib.sha256(encoded).hexdigest()[:16]}"
        return cls(
            evidence_id=evidence_id,
            source=source,
            file_path=norm_path,
            line_range=line_range,
            symbol=symbol,
            property_or_contract=property_or_contract,
            confidence=confidence,
            description=description.strip(),
            limitations=limitations or [],
            metadata=metadata or {},
        )
