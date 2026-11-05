"""Tests for opt-in, hash-only evaluation observability."""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

from pydantic import SecretStr
from typer.testing import CliRunner

from polaris.cli import app
from polaris.core.models import FindingCategory, LineRange, Severity
from polaris.evaluation.models import EvaluationFixture, ExpectedFindingSpec
from polaris.evaluation.runner import evaluate_corpus
from polaris.providers.nvidia import NvidiaProvider


def _fixture() -> EvaluationFixture:
    return EvaluationFixture(
        case_id="observability-case",
        description="A concrete division-by-zero regression.",
        diff_text=(
            "diff --git a/maths.py b/maths.py\n"
            "--- a/maths.py\n"
            "+++ b/maths.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def divide(a, b):\n"
            "-    return 0 if b == 0 else a / b\n"
            "+    return a / b\n"
        ),
        file_contents={"maths.py": "def divide(a, b):\n    return a / b\n"},
        expected_findings=[
            ExpectedFindingSpec(
                file_path="maths.py",
                line_range=LineRange(start_line=2, end_line=2),
                category=FindingCategory.BOUNDARY_CONDITION,
                severity=Severity.HIGH,
            )
        ],
    )


def test_observability_is_opt_in_and_hashes_never_store_prompt_or_response() -> None:
    secret = "nvapi-not-a-real-secret"
    raw_content = '{"findings": []}'

    def transport(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        return 200, {}, json.dumps(
            {
                "choices": [{"message": {"content": raw_content}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
            }
        )

    provider = NvidiaProvider(api_key=SecretStr(secret), max_retries=0, transport_fn=transport)
    plain = evaluate_corpus([_fixture()], provider, force_end_to_end=True)
    assert plain.case_results[0].observability is None

    observed = evaluate_corpus([_fixture()], provider, force_end_to_end=True, observability=True)
    telemetry = observed.case_results[0].observability
    assert telemetry is not None
    assert len(telemetry.attempts) == 1
    attempt = telemetry.attempts[0]
    assert len(attempt.prompt_hash) == 64
    assert len(attempt.response_hash or "") == 64
    serialized = telemetry.model_dump_json()
    assert secret not in serialized
    assert raw_content not in serialized


def test_cli_writes_observability_only_when_explicitly_requested(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps([_fixture().model_dump(mode="json")]), encoding="utf-8")
    output_path = tmp_path / "telemetry.json"
    result = CliRunner().invoke(
        app,
        [
            "evaluate",
            "--fixtures",
            str(fixture_path),
            "--end-to-end",
            "--observability-file",
            str(output_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert output_path.exists()
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["case_results"][0]["observability"]["provider"] == "fake"


def test_observability_records_retry_and_timeout_without_error_body() -> None:
    def timeout_transport(_request: object, _timeout: float) -> tuple[int, dict[str, str], str]:
        raise urllib.error.URLError("connection timed out")

    provider = NvidiaProvider(
        api_key=SecretStr("nvapi-not-a-real-secret"),
        max_retries=1,
        sleep_fn=lambda _: None,
        transport_fn=timeout_transport,
    )
    summary = evaluate_corpus([_fixture()], provider, force_end_to_end=True, observability=True)
    telemetry = summary.case_results[0].observability
    assert telemetry is not None
    assert [item.attempt_number for item in telemetry.attempts] == [1, 2]
    assert telemetry.attempts[0].retry_reason == "timeout"
    assert telemetry.attempts[-1].error_category == "timeout"
    assert all(item.response_hash is None for item in telemetry.attempts)
