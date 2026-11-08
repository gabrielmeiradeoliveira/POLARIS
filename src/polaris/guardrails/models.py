"""Data models and evidence definitions for POLARIS Security Guardrail Engine."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polaris.core.models import FindingCategory, LineRange, Severity


class GuardrailConfidence(StrEnum):
    """Certainty level for deterministically evaluated security properties.

    - CONFIRMED: Formally demonstrated through AST semantic proof within the supported Python subset.
    - SUSPECTED: Relevant indicator present, but analysis cannot prove global violation (e.g. dynamic state).
    - UNKNOWN: Insufficient static information or out-of-scope construct.
    """

    CONFIRMED = "confirmed"
    SUSPECTED = "suspected"
    UNKNOWN = "unknown"


class GuardrailEvidence(BaseModel):
    """Structured, reproducible evidence backing a deterministic security finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(..., description="Deterministic rule identifier (e.g. SEC-AUTH-001).")
    symbol: str = Field(..., description="Name of the affected function or symbol.")
    file_path: str = Field(..., description="Repository-relative path of the affected file.")
    line_range: LineRange = Field(..., description="Affected line range.")
    before_predicate: str | None = Field(default=None, description="Decompiled/normalized predicate prior to change.")
    after_predicate: str = Field(..., description="Decompiled/normalized predicate after change.")
    confidence: GuardrailConfidence = Field(..., description="Proof level of certainty.")
    reason: str = Field(..., description="Clear explanation of the demonstrated vulnerability or suspicion.")
    context_details: dict[str, Any] = Field(default_factory=dict, description="Supplementary structured AST metadata.")


class SecurityFinding(BaseModel):
    """Deterministic security finding produced by the Security Guardrail Engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str = Field(..., description="Deterministic stable identifier.")
    rule_id: str = Field(..., description="Rule identifier.")
    category: FindingCategory = Field(default=FindingCategory.LOGIC_ERROR)
    severity: Severity = Field(default=Severity.HIGH)
    file_path: str = Field(...)
    line_range: LineRange
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=4000)
    evidence: GuardrailEvidence
