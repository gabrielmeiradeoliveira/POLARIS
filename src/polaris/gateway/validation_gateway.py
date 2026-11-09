"""Token-Optimized AI Validation Gateway (GOAL 34).

Enforces strict AI skip policy, token budgeting, prompt compression,
and persistent caching before any LLM validation pass is triggered.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from polaris.core.models import BudgetTracker
from polaris.evidence.platform import CanonicalSecurityFinding


class AISkipReason(StrEnum):
    """Reason why an AI validation pass was safely skipped."""

    DETERMINISTIC_CONFIRMED = "DETERMINISTIC_CONFIRMED"
    LOW_RISK_THRESHOLD = "LOW_RISK_THRESHOLD"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    CACHE_HIT = "CACHE_HIT"
    OFFLINE_POLICY = "OFFLINE_POLICY"


class GatewayValidationDecision(BaseModel):
    """Decision produced by the gateway regarding whether AI should be invoked."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    should_call_ai: bool
    skip_reason: AISkipReason | None = None
    cache_key: str = ""
    allocated_tokens: int = 0
    compressed_prompt: str = ""


class AIValidationGateway:
    """Manages token economics, caching, and safe skip decisions for AI validation."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._in_memory_cache: dict[str, dict[str, Any]] = {}

    def compute_cache_key(self, finding: CanonicalSecurityFinding, diff_snippet: str) -> str:
        """Derive stable SHA-256 cache key from finding evidence and diff snippet."""
        seed = f"{finding.finding_id}::{finding.rule_or_cve}::{diff_snippet.strip()}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def evaluate(
        self,
        finding: CanonicalSecurityFinding,
        diff_snippet: str,
        tracker: BudgetTracker,
        force_ai: bool = False,
    ) -> GatewayValidationDecision:
        """Evaluate whether to call AI, skip, or reuse cache."""
        cache_key = self.compute_cache_key(finding, diff_snippet)

        # 1. Cache hit check
        if cache_key in self._in_memory_cache:
            return GatewayValidationDecision(
                should_call_ai=False,
                skip_reason=AISkipReason.CACHE_HIT,
                cache_key=cache_key,
            )

        # 2. Skip if finding is already 100% deterministically confirmed with high confidence and no force_ai
        if not force_ai and finding.confidence == "CONFIRMED" and finding.severity != "CRITICAL":
            return GatewayValidationDecision(
                should_call_ai=False,
                skip_reason=AISkipReason.DETERMINISTIC_CONFIRMED,
                cache_key=cache_key,
            )

        # 3. Budget availability check (fail-closed)
        remaining_tokens = tracker.budget.max_total_tokens - tracker.usage.total_tokens
        if remaining_tokens < 300 or tracker.requests_made >= tracker.budget.max_requests:
            return GatewayValidationDecision(
                should_call_ai=False,
                skip_reason=AISkipReason.BUDGET_EXHAUSTED,
                cache_key=cache_key,
            )

        # 4. Context compression: synthesize minimal prompt
        compressed_prompt = (
            f"Validate finding: {finding.title}\n"
            f"Rule: {finding.rule_or_cve}\n"
            f"File: {finding.file_path}:{finding.line}\n"
            f"Diff snippet:\n{diff_snippet[:500]}\n"
        )
        allocated = min(500, remaining_tokens)

        return GatewayValidationDecision(
            should_call_ai=True,
            cache_key=cache_key,
            allocated_tokens=allocated,
            compressed_prompt=compressed_prompt,
        )

    def record_cache(self, cache_key: str, response_payload: dict[str, Any]) -> None:
        """Store validated response in cache."""
        self._in_memory_cache[cache_key] = response_payload
