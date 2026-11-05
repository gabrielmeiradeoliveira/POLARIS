"""Tests for NVIDIA provider failure diagnostics, error categorization, and CLI reporting."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from polaris.cli import app
from polaris.core.errors import ProviderError
from polaris.core.models import BudgetTracker, ExecutionBudget, FindingCategory, LineRange, Severity
from polaris.evaluation.models import EvaluationFixture, ExpectedFindingSpec
from polaris.evaluation.runner import evaluate_corpus
from polaris.providers.base import ProviderRequest
from polaris.providers.nvidia import NvidiaProvider
from polaris.quota.store import UsageStore

runner = CliRunner()

SAMPLE_DIFF = """diff --git a/src/math.py b/src/math.py
--- a/src/math.py
+++ b/src/math.py
@@ -1,3 +1,3 @@
 def divide(a, b):
-    return a / b if b != 0 else 0
+    return a / b
"""

SAMPLE_FIXTURE = EvaluationFixture(
    case_id="nvidia-diag-case-01",
    description="Division by zero bug introduction",
    diff_text=SAMPLE_DIFF,
    file_contents={"src/math.py": "def divide(a, b):\n    return a / b\n"},
    expected_findings=[
        ExpectedFindingSpec(
            category=FindingCategory.CORRECTNESS,
            severity=Severity.HIGH,
            file_path="src/math.py",
            line_range=LineRange(start_line=2, end_line=2),
        )
    ],
    repository="https://github.com/example/repo",
    commit_id="abcdef1234567890",
    provenance="synthetic_reconstruction",
    suitable_for_live_benchmark=True,
)


def _make_fixture_list() -> list[EvaluationFixture]:
    return [SAMPLE_FIXTURE.model_copy(deep=True)]


def _persisted_diagnostic(tmp_path: Any, transport: Any) -> dict[str, Any]:
    store = UsageStore(tmp_path / "usage.sqlite3")
    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-test-key"),
        budget=ExecutionBudget(max_requests=1, max_total_tokens=1000),
        usage_store=store,
        quota_scope="diagnostics",
        max_retries=0,
        transport_fn=transport,
    )
    with pytest.raises(ProviderError):
        provider.generate(ProviderRequest(system_prompt="system", user_prompt="public diff", max_output_tokens=64))
    with store._connect() as conn:
        row = conn.execute("SELECT * FROM attempt_diagnostics").fetchone()
    return dict(row)


def test_connection_timeout_diagnostics_and_zero_fn() -> None:
    secret = "nvapi-SuperSecretTestKey123"

    def timeout_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        raise urllib.error.URLError("Connection timed out")

    provider = NvidiaProvider(
        api_key=SecretStr(secret),
        max_retries=0,
        transport_fn=timeout_transport,
    )

    fixtures = _make_fixture_list()
    summary = evaluate_corpus(
        fixtures=fixtures,
        provider=provider,
        force_end_to_end=True,
    )

    assert summary.successful_cases == 0
    assert summary.api_failed_cases == 1
    assert summary.failed_cases == 1
    assert summary.true_positives == 0
    assert summary.false_positives == 0
    assert summary.false_negatives == 0
    assert summary.precision is None
    assert summary.recall is None

    res = summary.case_results[0]
    assert res.status == "failed"
    assert res.error_category == "timeout"
    assert res.retries_attempted == 0
    assert secret not in str(res.error)


def test_read_timeout_diagnostics_and_zero_fn() -> None:
    secret = "nvapi-SuperSecretTestKey123"

    def read_timeout_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        raise TimeoutError("The read operation timed out")

    provider = NvidiaProvider(
        api_key=SecretStr(secret),
        max_retries=0,
        transport_fn=read_timeout_transport,
    )

    fixtures = _make_fixture_list()
    summary = evaluate_corpus(
        fixtures=fixtures,
        provider=provider,
        force_end_to_end=True,
    )

    assert summary.failed_cases == 1
    assert summary.false_negatives == 0
    res = summary.case_results[0]
    assert res.status == "failed"
    assert res.error_category == "timeout"


def test_persists_timeout_diagnostic_before_cli_exit(tmp_path: Any) -> None:
    def timeout_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        raise TimeoutError("timed out")

    diagnostic = _persisted_diagnostic(tmp_path, timeout_transport)
    assert diagnostic["state"] == "uncertain"
    assert diagnostic["error_category"] == "timeout"
    assert diagnostic["configured_attempt_timeout_seconds"] == 60.0
    assert diagnostic["response_hash"] is None
    assert diagnostic["prompt_hash"] is not None


def test_persists_connection_and_missing_response_diagnostics(tmp_path: Any) -> None:
    def connection_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        raise urllib.error.URLError("connection reset")

    diagnostic = _persisted_diagnostic(tmp_path, connection_transport)
    assert diagnostic["state"] == "uncertain"
    assert diagnostic["error_category"] == "connection_error"
    assert diagnostic["http_status"] is None
    assert diagnostic["response_hash"] is None


def test_bound_tracker_persists_transport_failure_without_provider_store(tmp_path: Any) -> None:
    store = UsageStore(tmp_path / "usage.sqlite3")
    budget = ExecutionBudget(max_requests=1, max_total_tokens=1000)

    def timeout_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        raise TimeoutError("timed out")

    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-test-key"), budget=budget, max_retries=0, transport_fn=timeout_transport
    )
    provider.bind_tracker(
        BudgetTracker(budget, usage_store=store, provider_name="nvidia", model_name=provider.model_name)
    )
    with pytest.raises(ProviderError):
        provider.generate(ProviderRequest(system_prompt="system", user_prompt="public diff", max_output_tokens=64))
    with store._connect() as conn:
        row = conn.execute(
            "SELECT u.status, d.error_category FROM usage_records u "
            "JOIN attempt_diagnostics d ON d.reservation_id = u.reservation_id"
        ).fetchone()
    assert tuple(row) == ("uncertain", "timeout")


def test_pre_send_payload_error_does_not_reserve_uncertain_usage(tmp_path: Any, monkeypatch: Any) -> None:
    store = UsageStore(tmp_path / "usage.sqlite3")
    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-test-key"),
        budget=ExecutionBudget(max_requests=1, max_total_tokens=1000),
        usage_store=store,
        max_retries=0,
    )

    def payload_error(_request: ProviderRequest) -> bytes:
        raise ValueError("payload construction failed")

    monkeypatch.setattr(provider, "_build_payload", payload_error)
    with pytest.raises(ValueError, match="payload construction failed"):
        provider.generate(ProviderRequest(system_prompt="system", user_prompt="public diff", max_output_tokens=64))
    with store._connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM usage_records").fetchone()[0]
    assert count == 0


def test_cli_exit_persists_timeout_diagnostic(temp_git_repo: Any, tmp_path: Any, monkeypatch: Any) -> None:
    (temp_git_repo / "src" / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    secret = "nvapi-cli-timeout-key"
    monkeypatch.setenv("NVIDIA_API_KEY", secret)
    monkeypatch.setenv("POLARIS_USAGE_DB_PATH", str(tmp_path / "cli_usage.sqlite3"))

    def timeout_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        raise TimeoutError("timed out")

    real_provider_init = NvidiaProvider.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.update(transport_fn=timeout_transport, max_retries=0)
        real_provider_init(self, *args, **kwargs)

    monkeypatch.setattr(NvidiaProvider, "__init__", patched_init)
    result = runner.invoke(
        app,
        [
            "review",
            "--repo",
            str(temp_git_repo),
            "--base",
            "HEAD",
            "--provider",
            "nvidia",
            "--allow-external",
            "--no-context",
            "--max-requests",
            "1",
        ],
    )

    assert result.exit_code == 4
    assert secret not in result.stdout
    store = UsageStore(tmp_path / "cli_usage.sqlite3")
    with store._connect() as conn:
        diagnostic = conn.execute(
            "SELECT u.status, d.state, d.error_category, d.response_hash FROM usage_records u "
            "JOIN attempt_diagnostics d ON d.reservation_id = u.reservation_id"
        ).fetchone()
    assert tuple(diagnostic) == ("uncertain", "uncertain", "timeout", None)


def test_http_429_rate_limit_diagnostics() -> None:
    secret = "nvapi-SuperSecretTestKey123"

    def rate_limit_transport(req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=429,
            msg="Too Many Requests",
            hdrs=MagicMock(items=lambda: [("Retry-After", "5")]),
            fp=None,
        )

    provider = NvidiaProvider(
        api_key=SecretStr(secret),
        max_retries=0,
        sleep_fn=lambda _: None,
        transport_fn=rate_limit_transport,
    )

    fixtures = _make_fixture_list()
    summary = evaluate_corpus(
        fixtures=fixtures,
        provider=provider,
        force_end_to_end=True,
    )

    assert summary.failed_cases == 1
    assert summary.false_negatives == 0
    res = summary.case_results[0]
    assert res.status == "failed"
    assert res.error_category == "rate_limit"
    assert res.http_status == 429


def test_http_500_server_error_diagnostics() -> None:
    secret = "nvapi-SuperSecretTestKey123"

    def server_error_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        return 500, {}, "Internal server error encountered"

    provider = NvidiaProvider(
        api_key=SecretStr(secret),
        max_retries=0,
        transport_fn=server_error_transport,
    )

    fixtures = _make_fixture_list()
    summary = evaluate_corpus(
        fixtures=fixtures,
        provider=provider,
        force_end_to_end=True,
    )

    assert summary.failed_cases == 1
    assert summary.false_negatives == 0
    res = summary.case_results[0]
    assert res.status == "failed"
    assert res.error_category == "server_error"
    assert res.http_status == 500


def test_malformed_response_diagnostics() -> None:
    secret = "nvapi-SuperSecretTestKey123"

    def malformed_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        return 200, {"content-type": "application/json"}, "NOT VALID JSON {{"

    provider = NvidiaProvider(
        api_key=SecretStr(secret),
        max_retries=0,
        transport_fn=malformed_transport,
    )

    fixtures = _make_fixture_list()
    summary = evaluate_corpus(
        fixtures=fixtures,
        provider=provider,
        force_end_to_end=True,
    )

    assert summary.failed_cases == 1
    assert summary.false_negatives == 0
    res = summary.case_results[0]
    assert res.status == "failed"
    assert res.error_category == "invalid_response"


def test_successful_nvidia_response() -> None:
    secret = "nvapi-SuperSecretTestKey123"
    valid_content = json.dumps(
        {
            "findings": [
                {
                    "category": "correctness",
                    "severity": "high",
                    "confidence": "high",
                    "file_path": "src/math.py",
                    "start_line": 2,
                    "end_line": 2,
                    "title": "Unchecked division by zero",
                    "description": "Division by zero without guard",
                    "evidence": "return a / b",
                }
            ]
        }
    )

    def success_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        body = json.dumps(
            {
                "id": "chatcmpl-test",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": valid_content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 150,
                    "completion_tokens": 40,
                    "total_tokens": 190,
                },
            }
        )
        return 200, {"content-type": "application/json"}, body

    provider = NvidiaProvider(
        api_key=SecretStr(secret),
        max_retries=0,
        transport_fn=success_transport,
    )

    fixtures = _make_fixture_list()
    summary = evaluate_corpus(
        fixtures=fixtures,
        provider=provider,
        force_end_to_end=True,
    )

    assert summary.successful_cases == 1
    assert summary.failed_cases == 0
    assert summary.true_positives == 1
    assert summary.false_positives == 0
    assert summary.false_negatives == 0
    assert summary.precision == 1.0
    assert summary.recall == 1.0

    res = summary.case_results[0]
    assert res.status == "completed"
    assert res.error_category is None
    assert res.http_status is None
    assert res.retries_attempted == 0


def test_cli_diagnostics_formatting_and_secret_redaction(tmp_path: Any, monkeypatch: Any) -> None:
    secret = "nvapi-SuperSecretKeyToNeverLeak"
    fixture_file = tmp_path / "test_fixture.json"
    fixture_file.write_text(json.dumps([SAMPLE_FIXTURE.model_dump(mode="json")]), encoding="utf-8")

    def failing_transport(_req: urllib.request.Request, _to: float) -> tuple[int, dict[str, str], str]:
        raise urllib.error.HTTPError(
            url="https://integrate.api.nvidia.com/v1/chat/completions",
            code=503,
            msg=f"Service unavailable for key {secret}",
            hdrs=MagicMock(items=lambda: []),
            fp=None,
        )

    monkeypatch.setenv("NVIDIA_API_KEY", secret)
    monkeypatch.setenv("POLARIS_USAGE_DB_PATH", str(tmp_path / "test_usage.sqlite3"))

    real_provider_init = NvidiaProvider.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["transport_fn"] = failing_transport
        kwargs["max_retries"] = 0
        kwargs["sleep_fn"] = lambda _: None
        real_provider_init(self, *args, **kwargs)

    monkeypatch.setattr(NvidiaProvider, "__init__", patched_init)

    result = runner.invoke(
        app,
        [
            "evaluate",
            "--provider",
            "nvidia",
            "--fixtures",
            str(fixture_file),
            "--end-to-end",
            "--allow-external",
            "--max-cases",
            "1",
            "--max-requests",
            "1",
        ],
    )

    assert result.exit_code == 0
    output = result.stdout
    assert "Failed Case Diagnostics:" in output
    assert "Case ID          : nvidia-diag-case-01" in output
    assert "Status           : failed" in output
    assert "Error Category   : server_error" in output
    assert "HTTP Status      : 503" in output
    assert "Duration         :" in output
    assert "Retries          : 0" in output
    assert secret not in output
    assert "[REDACTED]" in output
    store = UsageStore(tmp_path / "test_usage.sqlite3")
    with store._connect() as conn:
        diagnostic = conn.execute("SELECT state, error_category, http_status FROM attempt_diagnostics").fetchone()
    assert tuple(diagnostic) == ("failed", "server_error", 503)
