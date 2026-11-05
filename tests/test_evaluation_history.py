"""Offline integrity and metrics tests for append-only validation history."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from polaris.cli import app
from polaris.core.models import CandidateFinding, Confidence, FindingCategory, LineRange, Severity
from polaris.evaluation.history import (
    CorpusKind,
    DuplicateHistoryRunError,
    FindingValidationRecord,
    ValidationOutcome,
    VerificationMethod,
    append_manifest,
    build_manifest,
    calibration_metrics,
    load_manifests,
    manifest_payload_hash,
    trend_summary,
    validation_metrics,
    write_trend_reports,
)
from polaris.evaluation.models import EvaluationFixture, ExpectedFindingSpec
from polaris.evaluation.runner import evaluate_corpus
from polaris.providers.fake import FakeProvider


def _fixture() -> EvaluationFixture:
    return EvaluationFixture(
        case_id="history-case",
        description="A deterministic division-by-zero case.",
        diff_text=(
            "diff --git a/math.py b/math.py\n"
            "--- a/math.py\n"
            "+++ b/math.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def divide(a, b):\n"
            "-    return 0 if b == 0 else a / b\n"
            "+    return a / b\n"
        ),
        file_contents={"math.py": "def divide(a, b):\n    return a / b\n"},
        expected_findings=[
            ExpectedFindingSpec(
                file_path="math.py",
                line_range=LineRange(start_line=2, end_line=2),
                category=FindingCategory.BOUNDARY_CONDITION,
            )
        ],
        candidate_findings=[
            CandidateFinding(
                category=FindingCategory.BOUNDARY_CONDITION,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                file_path="math.py",
                start_line=2,
                end_line=2,
                title="Division by zero",
                description="The removed guard permits division by zero.",
                evidence="return a / b",
            )
        ],
    )


def _manifest(tmp_path: Path, run_id: str = "history-run-001"):
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps([_fixture().model_dump(mode="json")]), encoding="utf-8")
    summary = evaluate_corpus([_fixture()], provider=FakeProvider())
    return build_manifest(
        run_id=run_id,
        summary=summary,
        corpus_path=corpus,
        corpus_kind=CorpusKind.SYNTHETIC,
        provider="fake",
        model="fake-deterministic-v1",
        configuration="A",
        operational_limits={"max_requests": 10, "max_tokens": None},
        repo_root=tmp_path,
    )


def test_append_only_history_preserves_sanitized_finding_records(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    history = tmp_path / "history"

    target = append_manifest(history, manifest)
    loaded = load_manifests(history)

    assert target.exists()
    assert len(loaded) == 1
    record = loaded[0].findings[0]
    assert record.validation_outcome == ValidationOutcome.CONFIRMED
    assert record.verification_method == VerificationMethod.FIXTURE_GROUND_TRUTH
    assert record.declared_confidence == Confidence.HIGH
    assert record.numeric_probability is None
    assert loaded[0].summary.case_results == []
    assert loaded[0].validation_metrics is not None
    assert loaded[0].validation_metrics.confirmation_rate == 1.0
    assert loaded[0].calibration_metrics is not None
    assert loaded[0].calibration_metrics.available is False
    with pytest.raises(DuplicateHistoryRunError):
        append_manifest(history, manifest)


def test_finding_record_sanitizes_persisted_text() -> None:
    record = FindingValidationRecord(
        finding_id="dcd-sanitized",
        case_id="case",
        file_path="a.py",
        line_range=LineRange(start_line=1, end_line=1),
        category=FindingCategory.CORRECTNESS,
        evidence="Authorization: Bearer secret-value",
        validation_outcome=ValidationOutcome.UNCERTAIN,
        verification_method=VerificationMethod.HUMAN_REVIEW,
        decision_reason="token=not-for-history",
    )

    serialized = record.model_dump_json()
    assert "secret-value" not in serialized
    assert "not-for-history" not in serialized
    assert "[REDACTED]" in serialized


def test_history_integrity_detects_tampered_manifest(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    history = tmp_path / "history"
    target = append_manifest(history, manifest)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["provider"] = "tampered"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="manifest_sha256"):
        load_manifests(history)


def test_v1_manifest_hash_remains_verifiable_without_new_derived_fields(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path).model_copy(
        update={
            "schema_version": "1.0",
            "validation_metrics": None,
            "calibration_metrics": None,
            "manifest_sha256": None,
        }
    )
    legacy_hash = manifest_payload_hash(manifest)
    legacy = manifest.model_copy(update={"manifest_sha256": legacy_hash})
    history = tmp_path / "history"
    append_manifest(history, legacy)

    assert load_manifests(history)[0].schema_version == "1.0"


def test_validation_metrics_and_calibration_do_not_quantify_qualitative_confidence() -> None:
    qualitative = FindingValidationRecord(
        finding_id="dcd-qualitative",
        case_id="case",
        file_path="a.py",
        line_range=LineRange(start_line=1, end_line=1),
        category=FindingCategory.CORRECTNESS,
        declared_confidence=Confidence.HIGH,
        validation_outcome=ValidationOutcome.CONFIRMED,
        verification_method=VerificationMethod.HUMAN_REVIEW,
        decision_reason="Reviewed.",
    )
    unknown = qualitative.model_copy(
        update={"finding_id": "dcd-unknown", "validation_outcome": ValidationOutcome.NOT_ASSESSED}
    )
    metrics = validation_metrics([qualitative, unknown])
    calibration = calibration_metrics([qualitative, unknown], minimum_sample_size=1)

    assert metrics.validation_coverage == 0.5
    assert metrics.confirmation_rate == 1.0
    assert calibration.available is False
    assert calibration.sample_size == 0


def test_numeric_calibration_requires_assessed_samples_and_builds_reliability_bins() -> None:
    records = [
        FindingValidationRecord(
            finding_id=f"dcd-{index:012d}",
            case_id="case",
            file_path="a.py",
            line_range=LineRange(start_line=1, end_line=1),
            category=FindingCategory.CORRECTNESS,
            numeric_probability=0.8 if index % 2 == 0 else 0.2,
            validation_outcome=ValidationOutcome.CONFIRMED if index % 2 == 0 else ValidationOutcome.REJECTED,
            verification_method=VerificationMethod.EXECUTABLE_ORACLE,
            decision_reason="Oracle result.",
        )
        for index in range(20)
    ]

    calibration = calibration_metrics(records, minimum_sample_size=20, bins=2)

    assert calibration.available is True
    assert calibration.brier_score == 0.04
    assert sum(item.sample_size for item in calibration.bins) == 20


def test_trends_keep_real_and_synthetic_samples_separate(tmp_path: Path) -> None:
    history = tmp_path / "history"
    append_manifest(history, _manifest(tmp_path, "synthetic-run-001"))
    manifest_real = _manifest(tmp_path, "real-run-001").model_copy(update={"corpus_kind": CorpusKind.REAL})
    manifest_real = manifest_real.model_copy(update={"manifest_sha256": None})
    manifest_real = manifest_real.model_copy(update={"manifest_sha256": manifest_payload_hash(manifest_real)})
    append_manifest(history, manifest_real)

    manifests = load_manifests(history)
    synthetic = trend_summary(manifests, corpus_kind=CorpusKind.SYNTHETIC)
    real = trend_summary(manifests, corpus_kind=CorpusKind.REAL)
    json_path, markdown_path = write_trend_reports(history, run_id="trend-001")

    assert synthetic["run_count"] == 1
    assert real["run_count"] == 1
    assert json_path.exists() and markdown_path.exists()


def test_cli_can_append_history_without_external_calls(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps([_fixture().model_dump(mode="json")]), encoding="utf-8")
    history = tmp_path / "history"

    result = CliRunner().invoke(
        app,
        [
            "evaluate",
            "--provider",
            "fake",
            "--fixtures",
            str(fixture_path),
            "--history-dir",
            str(history),
            "--history-run-id",
            "cli-history-001",
            "--history-configuration",
            "A",
            "--history-corpus-kind",
            "synthetic",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (history / "manifests" / "cli-history-001.json").exists()
    assert (history / "reports" / "trend-cli-history-001.md").exists()
