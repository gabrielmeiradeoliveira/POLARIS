"""Data models and policy definitions for the POLARIS Hybrid Review Engine (GOAL 28.5)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polaris.core.models import TokenUsage
from polaris.intelligence.arbitration import ArbitrationResult, ExecutionState


class ReviewStrategy(StrEnum):
    """Review execution strategies supported by POLARIS."""

    DIRECT = "direct"     # Existing default pipeline (diff only or behavioral delta as configured)
    HYBRID = "hybrid"     # GOAL 28 OFF-first with evidence-justified selective ON and arbitration


class ExpansionDecision(BaseModel):
    """Deterministic policy decision on whether to invoke Arm ON (behavioral context)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    should_expand: bool
    reasons: list[str] = Field(default_factory=list)
    budget_permitted: bool = True
    quota_permitted: bool = True
    context_files_targeted: list[str] = Field(default_factory=list)


class HybridExecutionTelemetry(BaseModel):
    """Detailed execution telemetry for all phases of the hybrid review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy: ReviewStrategy = ReviewStrategy.HYBRID
    static_security_run: bool = True
    static_contract_run: bool = True
    off_arm_state: ExecutionState
    on_arm_state: ExecutionState
    expansion_decision: ExpansionDecision
    total_tokens: TokenUsage
    latency_ms: int
    partial_failure: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class HybridReviewResult(BaseModel):
    """Consolidated outcome of the hybrid review pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    arbitration: ArbitrationResult
    telemetry: HybridExecutionTelemetry
