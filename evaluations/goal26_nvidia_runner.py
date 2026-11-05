"""Bounded, sequential NVIDIA paired A/B runner for GOAL 26 Phase 3."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field

from polaris.context.context_models import ContextSelectionLimits
from polaris.core.config import PolarisConfig
from polaris.core.errors import BudgetExceededError
from polaris.core.models import BudgetTracker, ExecutionBudget
from polaris.evaluation.models import CaseEvaluationResult, EvaluationFixture
from polaris.evaluation.runner import evaluate_case, load_fixtures_from_file
from polaris.providers.base import LLMProvider, ProviderRequest
from polaris.providers.factory import create_provider
from polaris.quota.store import RequestStatus

MANIFEST_PATH = Path("evaluations/manifests/goal26-phase3-nvidia-paired.json")
MAX_OUTPUT_TOKENS = 4096


@dataclass(frozen=True)
class ArmOutcome:
    arm: str
    cases: tuple[CaseEvaluationResult, ...]
    stopped_reason: str | None


def request_wire_payload_bytes(request: Any, model: str) -> int:
    """Return the byte length of the NVIDIA JSON request body, excluding HTTP headers."""
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ],
        "temperature": request.temperature,
        "max_tokens": request.max_output_tokens,
    }
    return len(json.dumps(body).encode("utf-8"))


class ConservativeBudgetTracker(BudgetTracker):
    """Reserve a fixed upper input bound instead of a tokenizer estimate."""

    def __init__(self, *args: Any, input_reservation_tokens: int, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.input_reservation_tokens = input_reservation_tokens

    def available_output_tokens(self, estimated_prompt_tokens: int, requested_output_tokens: int, **kwargs: Any) -> int:
        return super().available_output_tokens(self.input_reservation_tokens, requested_output_tokens, **kwargs)

    def reserve_attempt(self, estimated_prompt_tokens: int = 0, **kwargs: Any) -> str | None:
        return super().reserve_attempt(self.input_reservation_tokens, **kwargs)

    def fail_attempt(self, reservation_id: str | None, **kwargs: Any) -> None:
        kwargs["estimated_prompt_tokens"] = self.input_reservation_tokens
        super().fail_attempt(reservation_id, **kwargs)


class CountedProviderRequest(ProviderRequest):
    exact_prompt_tokens: int = Field(ge=0)

    @property
    def estimated_prompt_tokens(self) -> int:
        return self.exact_prompt_tokens


class PayloadBoundProvider:
    """Reject oversized payloads and bind conservative reservations to the active tracker."""

    def __init__(self, provider: LLMProvider, *, max_wire_payload_bytes: int, token_counter=None) -> None:
        self.provider = provider
        self.max_wire_payload_bytes = max_wire_payload_bytes
        self.token_counter = token_counter
        self._tracker: BudgetTracker | None = None

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name

    @property
    def model_name(self) -> str:
        return self.provider.model_name

    def bind_tracker(self, tracker: BudgetTracker | None) -> None:
        self._tracker = tracker
        bind = getattr(self.provider, "bind_tracker", None)
        if callable(bind):
            bind(tracker)

    def generate(self, request: Any) -> Any:
        if request_wire_payload_bytes(request, self.model_name) > self.max_wire_payload_bytes:
            raise BudgetExceededError("NVIDIA request payload exceeds the frozen wire-payload limit.")
        if self.token_counter is not None:
            request = CountedProviderRequest(
                system_prompt=request.system_prompt,
                user_prompt=request.user_prompt,
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                response_json=request.response_json,
                exact_prompt_tokens=self.token_counter(request.system_prompt, request.user_prompt),
            )
        if self._tracker is None or callable(getattr(self.provider, "bind_tracker", None)):
            return self.provider.generate(request)
        reservation = self._tracker.reserve_attempt(
            request.estimated_prompt_tokens,
            reserved_output_tokens=request.max_output_tokens,
            provider_name=self.provider_name,
            model_name=self.model_name,
        )
        try:
            response = self.provider.generate(request)
        except Exception:
            self._tracker.fail_attempt(
                reservation,
                status=RequestStatus.FAILED,
                estimated_prompt_tokens=request.estimated_prompt_tokens,
            )
            raise
        self._tracker.complete_attempt(reservation, response.usage)
        return response


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict[str, Any], root: Path = Path(".")) -> list[EvaluationFixture]:
    if manifest["provider"] != "nvidia" or manifest["model"] != "minimaxai/minimax-m3.1-flash":
        raise ValueError("GOAL26 manifest must freeze the approved NVIDIA provider and model.")
    execution = manifest["execution"]
    if (execution["max_requests"], execution["max_total_tokens"], execution["max_retries"]) != (40, 100_000, 0):
        raise ValueError("GOAL26 manifest must retain the approved global limits.")
    input_reservation = manifest["input_reservation"]
    if input_reservation["max_wire_payload_bytes"] <= 0 or input_reservation["provider_tokenizer_overhead_tokens"] < 0:
        raise ValueError("GOAL26 manifest input reservation must be non-negative and bounded.")
    fixture_path = root / manifest["fixtures"]
    if hashlib.sha256(fixture_path.read_bytes()).hexdigest() != manifest["fixture_sha256"]:
        raise ValueError("GOAL26 fixture hash differs from the frozen manifest.")
    fixtures = load_fixtures_from_file(fixture_path)
    if [fixture.case_id for fixture in fixtures] != manifest["case_order"]:
        raise ValueError("GOAL26 fixture order differs from the frozen manifest.")
    return fixtures


def campaign_budget(manifest: dict[str, Any]) -> ExecutionBudget:
    execution = manifest["execution"]
    return ExecutionBudget(
        max_requests=execution["max_requests"],
        max_total_tokens=execution["max_total_tokens"],
        request_timeout_seconds=execution["request_timeout_seconds"],
        attempt_deadline_seconds=execution["attempt_deadline_seconds"],
        case_deadline_seconds=execution["case_deadline_seconds"],
        max_elapsed_seconds=execution["max_elapsed_seconds"],
        max_retries=execution["max_retries"],
    )


def _safe_case(result: CaseEvaluationResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "status": result.status,
        "operational_state": result.operational_state,
        "error_category": result.error_category,
        "http_status": result.http_status,
        "retries": result.retries_attempted,
        "tp": result.true_positives,
        "fp": result.false_positives,
        "fn": result.false_negatives,
        "latency_ms": result.latency_ms,
        "tokens": result.usage.model_dump(),
        "findings": [
            {
                "category": finding.category.value,
                "file_path": finding.file_path,
                "line_range": finding.line_range.model_dump(),
            }
            for finding in result.actual_findings
        ],
    }


def comparable_metrics(outcomes: tuple[ArmOutcome, ...]) -> dict[str, Any]:
    by_arm = {outcome.arm: {case.case_id: case for case in outcome.cases} for outcome in outcomes}
    paired = sorted(
        case_id
        for case_id, off in by_arm.get("off", {}).items()
        if off.status == "completed" and case_id in by_arm.get("on", {}) and by_arm["on"][case_id].status == "completed"
    )

    def metrics(arm: str) -> dict[str, Any]:
        cases = [by_arm.get(arm, {})[case_id] for case_id in paired]
        tp, fp, fn = (sum(getattr(case, name) for case in cases) for name in ("true_positives", "false_positives", "false_negatives"))
        return {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "recall": round(tp / (tp + fn), 4) if tp + fn else None,
        }

    return {"complete_pair_ids": paired, "off": metrics("off"), "on": metrics("on")}


def _write_partial(destination: Path, manifest: dict[str, Any], outcomes: list[ArmOutcome], tracker: BudgetTracker) -> None:
    payload = {
        "goal": manifest["goal"],
        "provider": manifest["provider"],
        "model": manifest["model"],
        "arms": [{"arm": outcome.arm, "stopped_reason": outcome.stopped_reason, "cases": [_safe_case(case) for case in outcome.cases]} for outcome in outcomes],
        "comparative_metrics": comparable_metrics(tuple(outcomes)),
        "global_usage": tracker.usage.model_dump(),
        "requests_made": tracker.requests_made,
    }
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)


def run_campaign(provider: LLMProvider, output_dir: Path, manifest: dict[str, Any] | None = None) -> tuple[ArmOutcome, ...]:
    """Run both arms with one tracker; an existing output path is never overwritten."""
    manifest = manifest or load_manifest()
    fixtures = validate_manifest(manifest)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing campaign output: {output_dir}")
    output_dir.mkdir(parents=True)
    budget = campaign_budget(manifest)
    input_reservation = manifest["input_reservation"]
    tracker = BudgetTracker(
        budget,
        usage_store=getattr(provider, "usage_store", None),
        provider_name=provider.provider_name,
        model_name=provider.model_name,
        quota_scope=getattr(provider, "quota_scope", "default"),
    )
    from evaluations.goal26_minimax_tokenizer import count_messages

    provider = PayloadBoundProvider(
        provider,
        max_wire_payload_bytes=input_reservation["max_wire_payload_bytes"],
        token_counter=count_messages,
    )
    limits = ContextSelectionLimits(
        max_context_tokens=manifest["context"]["max_context_tokens"],
        behavioral_delta_reserved_tokens=manifest["context"]["behavioral_delta_reserved_tokens"],
    )
    # Keep both arms adjacent for each fixture to minimize temporal provider drift.
    # A partial pair is never included in comparative metrics.
    outcomes_by_arm: dict[str, list[CaseEvaluationResult]] = {
        arm: [] for arm in manifest["arms"]
    }
    failures = 0
    stop: str | None = None
    for fixture in fixtures:
        for arm in manifest["arms"]:
            if stop:
                break
            result = evaluate_case(
                fixture,
                provider,
                budget=budget,
                tracker=tracker,
                force_end_to_end=True,
                behavioral_delta_enabled=arm == "on",
                production_parity=manifest["context"]["production_parity"],
                context_limits=limits,
                observability=True,
            )
            outcomes_by_arm[arm].append(result)
            if result.status == "budget_exhausted":
                stop = "budget_or_quota_exhausted"
            elif result.status != "completed":
                failures += 1
                if failures >= manifest["execution"]["repeated_operational_failure_threshold"]:
                    stop = "repeated_operational_failure"
            snapshot = [
                ArmOutcome(name, tuple(cases), stop)
                for name, cases in outcomes_by_arm.items()
            ]
            _write_partial(output_dir / "results.json", manifest, snapshot, tracker)
        if stop:
            break
    outcomes = [
        ArmOutcome(name, tuple(cases), stop)
        for name, cases in outcomes_by_arm.items()
    ]
    return tuple(outcomes)


def create_live_provider(manifest: dict[str, Any]) -> LLMProvider:
    budget = campaign_budget(manifest)
    config = PolarisConfig.from_env_and_args(
        provider="nvidia",
        model=manifest["model"],
        allow_external_code=True,
        max_tokens=budget.max_total_tokens,
        max_requests=budget.max_requests,
        max_retries=0,
        timeout_seconds=budget.request_timeout_seconds,
        attempt_deadline_seconds=budget.attempt_deadline_seconds,
        case_deadline_seconds=budget.case_deadline_seconds,
        max_elapsed_seconds=budget.max_elapsed_seconds,
        context_max_tokens=2000,
        behavioral_delta_reserved_tokens=500,
    )
    return create_provider(config)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    manifest = load_manifest()
    validate_manifest(manifest)
    run_campaign(create_live_provider(manifest), args.output_dir, manifest)


if __name__ == "__main__":
    main()
