"""Deterministic contracts for provider reliability controls and safe telemetry."""

from __future__ import annotations

import json
import urllib.error

import pytest
from pydantic import SecretStr

import deicide.providers.nvidia as nvidia_module
from deicide.core.errors import ProviderError, RateLimitError
from deicide.core.models import ExecutionBudget, FindingCategory, LineRange, Severity
from deicide.evaluation.models import EvaluationFixture, ExpectedFindingSpec
from deicide.evaluation.runner import evaluate_case, evaluate_corpus
from deicide.providers.base import ProviderRequest
from deicide.providers.nvidia import NvidiaProvider


def _request() -> ProviderRequest:
    return ProviderRequest(system_prompt="system", user_prompt="user")


def _response(content: str = '{"findings": []}') -> str:
    return json.dumps(
        {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
        }
    )


def _fixture() -> EvaluationFixture:
    return EvaluationFixture(
        case_id="provider-reliability",
        description="provider reliability fixture",
        diff_text=(
            "diff --git a/sample.py b/sample.py\n"
            "--- a/sample.py\n"
            "+++ b/sample.py\n"
            "@@ -1 +1 @@\n"
            "-value = 0\n"
            "+value = 1\n"
        ),
        file_contents={"sample.py": "value = 1\n"},
    )


def test_attempt_deadline_is_passed_to_transport_and_success_telemetry_is_complete() -> None:
    timeouts: list[float] = []

    def transport(_request: object, timeout: float) -> tuple[int, dict[str, str], str]:
        timeouts.append(timeout)
        return 200, {}, _response()

    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        timeout_seconds=30.0,
        budget=ExecutionBudget(attempt_deadline_seconds=4.5, max_total_tokens=1000),
        transport_fn=transport,
    )
    response = provider.generate(_request())

    assert response.usage.total_tokens == 14
    assert timeouts == [4.5]
    attempt = provider.last_attempts[0]
    assert attempt.configured_attempt_timeout_seconds == 4.5
    assert attempt.termination_reason == "completed"
    assert attempt.transport_duration_ms is not None
    assert attempt.error_category is None


def test_retry_after_is_exact_without_jitter_and_jitter_is_only_for_fallback_backoff() -> None:
    sleeps: list[float] = []
    calls = 0

    def rate_then_success(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return 429, {"Retry-After": "2.5"}, "untrusted provider body"
        return 200, {}, _response()

    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        max_retries=1,
        jitter_ratio=1.0,
        random_fn=lambda: 0.9,
        sleep_fn=sleeps.append,
        transport_fn=rate_then_success,
    )
    provider.generate(_request())
    assert sleeps == [2.5]
    assert provider.last_attempts[0].retry_reason == "HTTP 429"

    fallback = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        initial_backoff_seconds=2.0,
        jitter_ratio=0.5,
        random_fn=lambda: 0.5,
        transport_fn=lambda *_: (200, {}, _response()),
    )
    assert fallback._compute_backoff(1, None) == 5.0

    default_sleeps: list[float] = []
    default_calls = 0

    def server_then_success(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal default_calls
        default_calls += 1
        return (503, {}, "untrusted") if default_calls == 1 else (200, {}, _response())

    default_provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        max_retries=1,
        sleep_fn=default_sleeps.append,
        transport_fn=server_then_success,
    )
    default_provider.generate(_request())
    assert default_sleeps == [1.0]


def test_transport_duration_excludes_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0]
    monkeypatch.setattr(nvidia_module.time, "perf_counter_ns", lambda: clock[0])
    calls = 0

    def transport(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal calls
        calls += 1
        clock[0] += 5_000_000
        return (503, {}, "untrusted") if calls == 1 else (200, {}, _response())

    def backoff(_seconds: float) -> None:
        clock[0] += 500_000_000

    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        max_retries=1,
        sleep_fn=backoff,
        transport_fn=transport,
    )
    provider.generate(_request())

    first_attempt = provider.last_attempts[0]
    assert first_attempt.transport_duration_ms == 5
    assert first_attempt.latency_ms == 505


def test_default_transport_closes_response_when_read_raises_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stdlib response context manager must close even when a socket read fails."""
    closed = []

    class FailingResponse:
        status = 200
        headers: dict[str, str] = {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            closed.append((exc_type, exc))
            return False

        def read(self) -> bytes:
            raise TimeoutError("local read timeout")

    monkeypatch.setattr(nvidia_module.urllib.request, "urlopen", lambda *_args, **_kwargs: FailingResponse())
    with pytest.raises(TimeoutError, match="local read timeout"):
        NvidiaProvider._default_transport(object(), 1.0)  # type: ignore[arg-type]
    assert closed and closed[0][0] is TimeoutError


def test_retry_is_limited_to_retryable_failures_and_invalid_json_is_classified() -> None:
    forbidden_calls = 0

    def bad_request(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal forbidden_calls
        forbidden_calls += 1
        return 400, {}, "sensitive failure body"

    client_error = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        max_retries=2,
        transport_fn=bad_request,
    )
    with pytest.raises(ProviderError, match=r"HTTP 400") as client_exc:
        client_error.generate(_request())
    assert forbidden_calls == 1
    assert getattr(client_exc.value, "failure_category") == "client_error"
    assert "sensitive failure body" not in str(client_exc.value)

    invalid = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        transport_fn=lambda *_: (200, {}, "not valid json"),
    )
    with pytest.raises(ProviderError, match="invalid JSON") as invalid_exc:
        invalid.generate(_request())
    assert getattr(invalid_exc.value, "failure_category") == "invalid_response"
    assert invalid.last_attempts[0].termination_reason == "invalid_response"


def test_timeout_and_connection_error_are_distinct_and_budgeted_attempts_are_visible() -> None:
    for error, category in (
        (TimeoutError("read timed out"), "timeout"),
        (urllib.error.URLError("name resolution failed"), "connection_error"),
    ):
        provider = NvidiaProvider(
            api_key=SecretStr("nvapi-testing-key"),
            max_retries=0,
            budget=ExecutionBudget(max_total_tokens=1000, max_requests=1),
            transport_fn=lambda *_args, exc=error: (_ for _ in ()).throw(exc),
        )
        with pytest.raises(ProviderError) as exc_info:
            provider.generate(_request())
        assert getattr(exc_info.value, "failure_category") == category
        assert provider.last_attempts[0].error_category.value == category
        assert provider.last_attempts[0].usage is None


def test_case_deadline_after_provider_response_is_explicit_operational_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter((0.0, 0.0, 2.0))
    monkeypatch.setattr("deicide.evaluation.runner.time.monotonic", lambda: next(ticks))
    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        transport_fn=lambda *_: (200, {}, _response()),
    )

    result = evaluate_case(
        _fixture(),
        provider,
        force_end_to_end=True,
        budget=ExecutionBudget(case_deadline_seconds=1.0, max_total_tokens=1000),
        observability=True,
    )

    assert result.status == "budget_exhausted"
    assert result.operational_state == "budget_exhausted"
    assert result.error_category == "budget_exhausted"
    assert result.observability is not None
    assert result.observability.attempts is not None


def test_skipped_case_has_explicit_skipped_operational_state() -> None:
    skipped = _fixture().model_copy(update={"suitable_for_live_benchmark": False})
    provider = NvidiaProvider(api_key=SecretStr("nvapi-testing-key"), transport_fn=lambda *_: (200, {}, _response()))
    result = evaluate_case(skipped, provider, skip_unsuitable=True)
    assert result.status == "skipped"
    assert result.operational_state == "skipped"


def test_observable_failure_never_persists_secret_or_provider_body() -> None:
    secret = "nvapi-private-telemetry-secret"
    body = "provider response body must never persist"
    provider = NvidiaProvider(
        api_key=SecretStr(secret),
        transport_fn=lambda *_: (503, {}, f"{body} {secret}"),
    )

    summary = evaluate_corpus([_fixture()], provider, force_end_to_end=True, observability=True)
    result = summary.case_results[0]
    serialized = result.model_dump_json()

    assert result.operational_state == "provider_http_error"
    assert body not in serialized
    assert secret not in serialized
    assert result.observability is not None
    assert result.observability.attempts is not None
    assert result.observability.attempts[0].response_hash is None


def test_local_transport_baseline_and_reliability_controls_preserve_outcomes() -> None:
    """Compare deterministic local contracts only; this is not an NVIDIA reliability simulation."""
    finding_response = _response(
        json.dumps(
            {
                "findings": [
                    {
                        "category": "logic_error",
                        "severity": "medium",
                        "confidence": "high",
                        "file_path": "sample.py",
                        "start_line": 1,
                        "end_line": 1,
                        "title": "Incorrect value assignment",
                        "description": "The changed assignment produces the wrong value for callers.",
                        "evidence": "value = 1",
                    }
                ]
            }
        )
    )
    fixture = _fixture().model_copy(
        update={
            "expected_findings": [
                ExpectedFindingSpec(
                    file_path="sample.py",
                    line_range=LineRange(start_line=1, end_line=1),
                    category=FindingCategory.LOGIC_ERROR,
                    severity=Severity.MEDIUM,
                )
            ]
        }
    )
    baseline_timeouts: list[float] = []
    controlled_timeouts: list[float] = []
    baseline = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        timeout_seconds=30.0,
        transport_fn=lambda _request, timeout: (baseline_timeouts.append(timeout) or (200, {}, finding_response)),
    )
    controlled = NvidiaProvider(
        api_key=SecretStr("nvapi-testing-key"),
        timeout_seconds=30.0,
        budget=ExecutionBudget(attempt_deadline_seconds=4.5, max_total_tokens=1000),
        transport_fn=lambda _request, timeout: (controlled_timeouts.append(timeout) or (200, {}, finding_response)),
    )

    baseline_result = evaluate_case(fixture, baseline, force_end_to_end=True)
    controlled_result = evaluate_case(
        fixture,
        controlled,
        force_end_to_end=True,
        budget=ExecutionBudget(attempt_deadline_seconds=4.5, max_total_tokens=1000),
    )

    assert (controlled_result.status, controlled_result.true_positives, controlled_result.false_positives) == (
        baseline_result.status,
        baseline_result.true_positives,
        baseline_result.false_positives,
    )
    assert baseline_timeouts == [30.0]
    assert controlled_timeouts == [4.5]

    failure_calls = 0

    def local_timeout(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        nonlocal failure_calls
        failure_calls += 1
        raise TimeoutError("local deterministic timeout")

    failed = evaluate_case(
        _fixture(),
        NvidiaProvider(
            api_key=SecretStr("nvapi-testing-key"),
            max_retries=1,
            sleep_fn=lambda _seconds: None,
            transport_fn=local_timeout,
        ),
        force_end_to_end=True,
    )
    assert failure_calls == 2
    assert failed.status == "failed"
    assert failed.operational_state == "provider_timeout"
