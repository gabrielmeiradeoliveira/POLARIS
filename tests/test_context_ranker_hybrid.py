"""Tests specifically demonstrating ContextRanker invocation and ordering inside HybridReviewOrchestrator."""

from __future__ import annotations

import pytest

from polaris.core.models import (
    BudgetTracker,
    CandidateFinding,
    Confidence,
    ExecutionBudget,
    FindingCategory,
    Severity,
)
from polaris.providers.fake import FakeProvider
from polaris.review.engine import HybridReviewOrchestrator
from tests.test_hybrid_orchestrator import ScriptedProvider


def test_context_ranker_ordering_in_arm_on():
    """Verify that ContextRanker prioritizes targeted files over secondary files with deterministic headers."""
    recorded_prompt = []

    class InspectingProvider(ScriptedProvider):
        def generate(self, request):
            if "RANKED CONTEXT" in request.user_prompt:
                recorded_prompt.append(request.user_prompt)
            return super().generate(request)

    # Candidate that triggers expansion to related files
    off_cand = CandidateFinding(
        category=FindingCategory.NULL_HANDLING,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="service/main.py",
        start_line=1,
        end_line=1,
        title="Null handling required",
        description="Detailed description for null handling defect",
        evidence="Evidence line",
    )

    provider = InspectingProvider(off_findings=[off_cand])
    tracker = BudgetTracker(ExecutionBudget(max_total_tokens=10_000, max_requests=10))
    orchestrator = HybridReviewOrchestrator()

    related = {
        "service/caller_z.py": "# File Z\n",
        "service/main.py": "# Targeted main caller\n",
        "service/caller_a.py": "# File A\n",
    }

    result = orchestrator.run_review(
        changed_file="service/main.py",
        before_content="def run(): return 1\n",
        after_content="def run(): return None\n",
        diff_text="diff",
        provider=provider,
        tracker=tracker,
        related_files=related,
    )

    assert len(recorded_prompt) == 1
    prompt_text = recorded_prompt[0]

    # Verify that ContextRanker priority header for target file appears before secondary files
    target_pos = prompt_text.find("=== [ContextRanker Priority: TARGET] service/main.py ===")
    secondary_pos = prompt_text.find("=== [ContextRanker Priority: SECONDARY] service/caller_a.py ===")

    assert target_pos != -1
    assert secondary_pos != -1
    assert target_pos < secondary_pos
