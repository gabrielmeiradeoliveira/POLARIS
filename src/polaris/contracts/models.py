"""Data models and evidence definitions for Cross-File Contract Analysis (GOAL 28.3)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from polaris.core.models import FindingCategory, LineRange, Severity
from polaris.guardrails.models import GuardrailConfidence


class ContractKind(StrEnum):
    """Categorical kind of inferred return structure."""

    DICT_LITERAL = "dict_literal"
    SCALAR_OR_PASSTHROUGH = "scalar_or_passthrough"
    NONE = "none"
    UNKNOWN = "unknown"


class InferredContract(BaseModel):
    """Static description of an inferred return contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ContractKind
    guaranteed_keys: list[str] = Field(default_factory=list)
    raw_expression: str = Field(...)


class PropagationStep(BaseModel):
    """A step in an interprocedural propagation trail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_index: int
    file_path: str
    symbol: str
    line_number: int
    action: str = Field(..., description="Action taken (e.g., 'calls', 'returns_passthrough', 'indexes').")
    expression: str


class IncompatibilityEvidence(BaseModel):
    """Detailed evidence supporting a cross-file contract violation finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    origin_file: str
    origin_symbol: str
    origin_line: int
    before_contract: InferredContract | None
    after_contract: InferredContract
    consumer_file: str
    consumer_symbol: str
    consumer_line: int
    required_operation: str = Field(..., description="Operation attempted by consumer (e.g. index ['value']).")
    propagation_path: list[PropagationStep] = Field(default_factory=list)
    confidence: GuardrailConfidence
    reason: str
    limitations: list[str] = Field(default_factory=list)


class ContractFinding(BaseModel):
    """Structured contract finding produced by the Contract Analysis Engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str = "CONTRACT-001"
    category: FindingCategory = FindingCategory.TYPE_MISMATCH
    severity: Severity = Severity.HIGH
    file_path: str
    line_range: LineRange
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=4000)
    evidence: IncompatibilityEvidence
