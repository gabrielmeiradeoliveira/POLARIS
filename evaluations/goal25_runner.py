"""Frozen, bounded GOAL 25 static-versus-NVIDIA A/B experiment runner.

The runner intentionally persists metrics only: no source, prompts, model output,
or credentials are included in its result structures.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evaluations.fixtures.goal24_post_slice_holdout.catalog import CASES as POST_SLICE_CASES
from evaluations.fixtures.goal24_rc1.catalog import CATALOG
from evaluations.goal24_post_slice_holdout_runner import fixture_for as post_slice_fixture
from evaluations.goal24_runner import fixture_for as goal24_fixture
from tests.test_goal21_adversarial import _cases as goal21_cases
from tests.test_goal21_adversarial import _fixture as goal21_fixture
from tests.test_goal23_real_world import _cases as goal23_cases
from tests.test_goal23_real_world import _fixture as goal23_fixture

from polaris.core.models import ExecutionBudget
from polaris.evaluation.models import EvaluationFixture, EvaluationSummary
from polaris.evaluation.runner import evaluate_corpus
from polaris.providers.base import LLMProvider
from polaris.providers.fake import FakeProvider

# Frozen before the first live A/B call: two GOAL21, two GOAL23, six GOAL24
# (one positive/negative pair for each N1/N2/N3), and two post-slice cases.
SAMPLE_CASE_IDS: tuple[str, ...] = (
    "pos_auth_bypass",
    "neg_auth_enforced",
    "g23_pos_async_cancel_swallowed",
    "g23_neg_service_discount_refactor",
    "g24-api_auth-01",
    "g24-orders_payments-02",
    "g24-etl_replay-13",
    "g24-async_workers-14",
    "g24-orders_payments-37",
    "g24-etl_replay-38",
    "psh-pos-exception-swallowing",
    "psh-neg-data-flow-tenant",
)

PREFLIGHT_REQUESTS_ALREADY_USED = 1
MAX_ADDITIONAL_NVIDIA_REQUESTS = 12
MAX_OUTPUT_TOKENS_PER_REQUEST = 1_666


def goal25_budget() -> ExecutionBudget:
    """Return the hard caps approved for a sequential GOAL25 run."""
    return ExecutionBudget(
        max_requests=60,
        max_total_tokens=70_000,
        max_input_tokens=50_000,
        max_output_tokens=20_000,
        max_input_tokens_per_request=8_000,
        max_output_tokens_per_request=2_000,
        request_timeout_seconds=90.0,
        max_retries=1,
    )


def goal25_live_budget() -> ExecutionBudget:
    """Apply the stricter per-experiment call cap to the real A/B arm.

    The general GOAL25 caps still permit up to 60 requests across an execution,
    but this frozen twelve-case experiment is separately authorized for no more
    than twelve additional NVIDIA requests.  Retrying would consume a slot that
    belongs to a later case, so retries are disabled for this fixed sample.
    """
    return goal25_budget().model_copy(
        update={
            "max_requests": MAX_ADDITIONAL_NVIDIA_REQUESTS,
            "max_output_tokens_per_request": MAX_OUTPUT_TOKENS_PER_REQUEST,
            "max_retries": 0,
        }
    )


def frozen_sample() -> list[EvaluationFixture]:
    """Build the fixed stratified sample without modifying source corpora."""
    fixtures: dict[str, EvaluationFixture] = {}
    fixtures.update({str(case["id"]): goal21_fixture(case) for case in goal21_cases()})
    fixtures.update({str(case["id"]): goal23_fixture(case) for case in goal23_cases()})
    fixtures.update({case.id: goal24_fixture(case) for case in CATALOG})
    fixtures.update({case.id: post_slice_fixture(case) for case in POST_SLICE_CASES})
    return [fixtures[case_id] for case_id in SAMPLE_CASE_IDS]


@dataclass(frozen=True)
class SafeCaseResult:
    case_id: str
    tp: int
    fp: int
    fn: int
    status: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    retries: int
    rejected_findings: int


def safe_result(summary: EvaluationSummary, *, configuration: str, provider: str, model: str) -> dict[str, Any]:
    """Serialize metrics-only data suitable for GOAL25 results storage."""
    return {
        "configuration": configuration,
        "provider": provider,
        "model": model,
        "sample_case_ids": list(SAMPLE_CASE_IDS),
        "preflight_requests_already_used": PREFLIGHT_REQUESTS_ALREADY_USED,
        "summary": {
            "tp": summary.true_positives,
            "fp": summary.false_positives,
            "fn": summary.false_negatives,
            "precision": summary.precision,
            "recall": summary.recall,
            "f1": summary.f1_score,
            "negative_fp_rate": summary.false_positive_rate,
            "completion_rate": summary.completion_rate,
            "prompt_tokens": summary.usage.prompt_tokens,
            "completion_tokens": summary.usage.completion_tokens,
            "total_tokens": summary.usage.total_tokens,
            "usage_estimated": summary.usage.is_estimated,
            "total_latency_ms": summary.total_latency_ms,
            "average_latency_ms": summary.average_latency_ms,
            "failed_cases": summary.failed_cases,
            "duplicates_reduced": summary.duplicates_reduced,
            "legitimate_rejected": summary.legitimate_rejected,
        },
        "cases": [
            asdict(
                SafeCaseResult(
                    case_id=result.case_id,
                    tp=result.true_positives,
                    fp=result.false_positives,
                    fn=result.false_negatives,
                    status=result.status,
                    latency_ms=result.latency_ms,
                    prompt_tokens=result.usage.prompt_tokens,
                    completion_tokens=result.usage.completion_tokens,
                    total_tokens=result.usage.total_tokens,
                    retries=result.retries_attempted,
                    rejected_findings=len(result.diagnostics.rejected_candidates) if result.diagnostics else 0,
                )
            )
            for result in summary.case_results
        ],
    }


def run_static_only() -> EvaluationSummary:
    fixtures = frozen_sample()
    return evaluate_corpus(
        fixtures,
        FakeProvider(scripted_responses=["{}"] * len(fixtures)),
        force_end_to_end=True,
        behavioral_delta_enabled=False,
        budget=goal25_budget(),
    )


def run_hybrid(provider: LLMProvider) -> EvaluationSummary:
    """Run sequentially with the supplied real provider and approved budget."""
    return evaluate_corpus(
        frozen_sample(),
        provider,
        force_end_to_end=True,
        behavioral_delta_enabled=False,
        budget=goal25_live_budget(),
        observability=True,
    )


def write_safe_result(payload: dict[str, Any], destination: Path) -> None:
    """Persist metrics-only results; reject payloads that could expose code or secrets."""
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    forbidden_fields = ("prompt", "response", "api_key", "authorization", "diff_text", "file_contents")
    if any(f'"{field}"' in serialized.lower() for field in forbidden_fields):
        raise ValueError("GOAL25 result payload contains a forbidden telemetry field.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(serialized + "\n", encoding="utf-8")
    temporary.replace(destination)
