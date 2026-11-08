"""Comprehensive unit and offline integration tests for GOAL 27."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from evaluations.goal27_runner import (
    ArmOutcome,
    build_readiness_report,
    compare_paired_arms,
    compute_metrics,
    load_manifest,
    run_goal27_campaign,
    validate_manifest,
    write_checkpoint,
)

from polaris.core.models import BudgetTracker, ExecutionBudget, TokenUsage
from polaris.evaluation.models import CaseEvaluationResult
from polaris.providers.fake import FakeProvider


def test_manifest_validation_rejects_unsupported_version_or_campaign(tmp_path: Path) -> None:
    manifest = load_manifest()
    with pytest.raises(ValueError, match="schema_version"):
        validate_manifest({**manifest, "schema_version": 99})

    with pytest.raises(ValueError, match="campaign_id"):
        validate_manifest({**manifest, "campaign_id": "invalid-campaign"})


def test_manifest_validation_detects_prompt_and_dataset_drift(tmp_path: Path) -> None:
    manifest = load_manifest()
    with pytest.raises(ValueError, match="prompt drift"):
        validate_manifest({**manifest, "system_prompt_sha256": "0" * 64})

    with pytest.raises(ValueError, match="Fixture hash drift"):
        validate_manifest({**manifest, "fixture_sha256": "1" * 64})


def test_manifest_validation_rejects_unregistered_model(tmp_path: Path) -> None:
    manifest = load_manifest()
    with pytest.raises(ValueError, match="not in manifest candidate_models"):
        validate_manifest(manifest, selected_model_id="non-existent-llm")


def test_manifest_validation_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    manifest = load_manifest()
    fixtures_file = tmp_path / "dup_fixtures.json"
    dup_cases = [
        {"case_id": "case-01", "description": "d1", "diff_text": "", "file_contents": {}},
        {"case_id": "case-01", "description": "d2", "diff_text": "", "file_contents": {}},
    ]
    content = json.dumps(dup_cases).encode("utf-8")
    fixtures_file.write_bytes(content)

    manifest_dup = {
        **manifest,
        "fixtures": str(fixtures_file),
        "fixture_sha256": hashlib.sha256(content).hexdigest(),
        "case_order": ["case-01", "case-01"],
    }
    with pytest.raises(ValueError, match="Duplicate case IDs"):
        validate_manifest(manifest_dup)


def test_metrics_handles_zero_denominator_safely() -> None:
    # Empty cases: all metrics safely undefined (None), never artificial 100%
    empty_res = compute_metrics([])
    assert empty_res["completed_count"] == 0
    assert empty_res["precision"] is None
    assert empty_res["recall"] is None
    assert empty_res["f1"] is None
    assert empty_res["false_positives_per_review"] is None
    assert empty_res["true_positives_per_review"] is None
    assert empty_res["latency"]["mean_ms"] is None

    # Clean case only (0 TP, 0 FP, 0 FN): precision and recall are None
    clean_case = CaseEvaluationResult(
        case_id="clean-01",
        status="completed",
        true_positives=0,
        false_positives=0,
        false_negatives=0,
        latency_ms=10.0,
    )
    clean_res = compute_metrics([clean_case])
    assert clean_res["precision"] is None
    assert clean_res["recall"] is None
    assert clean_res["f1"] is None
    assert clean_res["false_positives_per_review"] == 0.0
    assert clean_res["true_positives_per_review"] == 0.0


def test_metrics_calculation_accuracy() -> None:
    case1 = CaseEvaluationResult(
        case_id="c1",
        status="completed",
        true_positives=2,
        false_positives=1,
        false_negatives=0,
        latency_ms=20.0,
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    case2 = CaseEvaluationResult(
        case_id="c2",
        status="completed",
        true_positives=1,
        false_positives=0,
        false_negatives=1,
        latency_ms=40.0,
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    metrics = compute_metrics([case1, case2])
    # TP=3, FP=1, FN=1
    assert metrics["tp"] == 3
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert metrics["precision"] == round(3 / 4, 4)  # 0.75
    assert metrics["recall"] == round(3 / 4, 4)     # 0.75
    assert metrics["f1"] == 0.75
    assert metrics["false_positives_per_review"] == 0.5
    assert metrics["true_positives_per_review"] == 1.5
    assert metrics["latency"]["mean_ms"] == 30.0
    assert metrics["tokens"]["total_tokens"] == 300


def test_paired_comparison_excludes_incomplete_pairs() -> None:
    case_a_off = CaseEvaluationResult(case_id="pair-01", status="completed", true_positives=1)
    case_a_on = CaseEvaluationResult(case_id="pair-01", status="completed", true_positives=1)
    # pair-02 is completed in OFF, but failed in ON
    case_b_off = CaseEvaluationResult(case_id="pair-02", status="completed", true_positives=1)
    case_b_on = CaseEvaluationResult(case_id="pair-02", status="failed", error_category="api_error")

    outcomes = (
        ArmOutcome("off", (case_a_off, case_b_off), None),
        ArmOutcome("on", (case_a_on, case_b_on), None),
    )
    comparison = compare_paired_arms(outcomes)
    assert comparison["complete_pair_ids"] == ["pair-01"]
    assert comparison["paired_case_count"] == 1
    # Only pair-01 is scored comparatively in off and on
    assert comparison["off"]["completed_count"] == 1
    assert comparison["on"]["completed_count"] == 1


def test_refuses_external_execution_without_explicit_authorization(tmp_path: Path) -> None:
    manifest = load_manifest()
    output_dir = tmp_path / "blocked_run"
    provider = FakeProvider()

    # When external_execution_authorized is false and is_simulated is false, must refuse
    with pytest.raises(RuntimeError, match="External execution is not authorized"):
        run_goal27_campaign(
            provider,
            output_dir,
            {**manifest, "external_execution_authorized": False},
            is_simulated=False,
        )


def test_atomic_pair_admission_stops_when_capacity_cannot_cover_full_pair(tmp_path: Path) -> None:
    manifest = load_manifest()
    output_dir = tmp_path / "low_budget_run"

    # Restrict budget so it cannot even cover 2 requests (1 pair)
    constrained_manifest = {
        **manifest,
        "execution": {
            **manifest["execution"],
            "max_requests": 1,  # Needs 2 requests for an OFF/ON pair
        },
    }
    provider = FakeProvider()
    outcomes = run_goal27_campaign(
        provider,
        output_dir,
        constrained_manifest,
        is_simulated=True,
    )
    assert outcomes[0].stopped_reason == "insufficient_capacity_for_complete_pair"
    assert len(outcomes[0].cases) == 0
    assert len(outcomes[1].cases) == 0


def test_checkpoint_resume_rejects_manifest_mismatch(tmp_path: Path) -> None:
    manifest = load_manifest()
    output_dir = tmp_path / "resume_mismatch"
    output_dir.mkdir()

    results_file = output_dir / "results.json"
    tracker = BudgetTracker(ExecutionBudget(max_requests=40, max_total_tokens=100000))
    model_spec = manifest["candidate_models"][0]
    outcomes = [ArmOutcome("off", (), None), ArmOutcome("on", (), None)]

    write_checkpoint(results_file, manifest, model_spec, outcomes, tracker, is_simulated=True)

    # Change manifest
    changed_manifest = {**manifest, "campaign_id": "goal27-real-world-model-selection", "goal": "Tampered"}
    provider = FakeProvider()
    with pytest.raises(ValueError, match="manifest SHA-256 does not match"):
        run_goal27_campaign(provider, output_dir, changed_manifest, resume=True, is_simulated=True)


def test_checkpoint_resume_continues_seamlessly_without_duplicate_requests(tmp_path: Path) -> None:
    manifest = load_manifest()
    model_spec, fixtures = validate_manifest(manifest)

    # Create subset manifest with 2 fixtures
    subset_fixtures = [fixtures[0].model_dump(mode="json"), fixtures[1].model_dump(mode="json")]
    fixtures_file = tmp_path / "subset.json"
    content = json.dumps(subset_fixtures).encode("utf-8")
    fixtures_file.write_bytes(content)

    manifest_subset = {
        **manifest,
        "fixtures": str(fixtures_file),
        "fixture_sha256": hashlib.sha256(content).hexdigest(),
        "case_order": [fixtures[0].case_id, fixtures[1].case_id],
    }

    output_dir = tmp_path / "resume_success"
    output_dir.mkdir()

    # Pre-populate checkpoint with completed pair 0
    case_0_off = CaseEvaluationResult(
        case_id=fixtures[0].case_id,
        status="completed",
        true_positives=1,
        usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    )
    case_0_on = CaseEvaluationResult(
        case_id=fixtures[0].case_id,
        status="completed",
        true_positives=1,
        usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    )
    tracker = BudgetTracker(ExecutionBudget(max_requests=40, max_total_tokens=100000))
    tracker.requests_made = 2
    tracker.usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)

    checkpoint_outcomes = [
        ArmOutcome("off", (case_0_off,), None),
        ArmOutcome("on", (case_0_on,), None),
    ]
    write_checkpoint(output_dir / "results.json", manifest_subset, model_spec, checkpoint_outcomes, tracker, is_simulated=True)

    provider = FakeProvider()
    outcomes = run_goal27_campaign(
        provider,
        output_dir,
        manifest_subset,
        resume=True,
        is_simulated=True,
    )

    # Both cases should now be present in both arms
    assert [c.case_id for c in outcomes[0].cases] == [fixtures[0].case_id, fixtures[1].case_id]
    assert [c.case_id for c in outcomes[1].cases] == [fixtures[0].case_id, fixtures[1].case_id]

    final_json = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert final_json["requests_made"] == 4
    assert final_json["is_simulated"] is True
    assert final_json["comparative_metrics"]["complete_pair_ids"] == [fixtures[0].case_id, fixtures[1].case_id]


def test_max_cases_limits_evaluation_run(tmp_path: Path) -> None:
    manifest = load_manifest()
    output_dir = tmp_path / "max_cases_run"
    provider = FakeProvider()
    outcomes = run_goal27_campaign(
        provider,
        output_dir,
        manifest,
        is_simulated=True,
        max_cases=2,
    )
    assert len(outcomes[0].cases) == 2
    assert len(outcomes[1].cases) == 2


def test_unauthorized_external_execution_raises_error(tmp_path: Path) -> None:
    manifest = load_manifest()
    unauth_manifest = {**manifest, "external_execution_authorized": False}
    output_dir = tmp_path / "unauth_run"
    provider = FakeProvider()
    with pytest.raises(RuntimeError, match="External execution is not authorized"):
        run_goal27_campaign(
            provider,
            output_dir,
            unauth_manifest,
            is_simulated=False,
        )


def test_resume_rolls_back_trailing_budget_exhausted_pair(tmp_path: Path) -> None:
    manifest = load_manifest()
    model_spec, fixtures = validate_manifest(manifest)

    subset_fixtures = [fixtures[0].model_dump(mode="json"), fixtures[1].model_dump(mode="json")]
    fixtures_file = tmp_path / "subset2.json"
    content = json.dumps(subset_fixtures).encode("utf-8")
    fixtures_file.write_bytes(content)

    manifest_subset = {
        **manifest,
        "fixtures": str(fixtures_file),
        "fixture_sha256": hashlib.sha256(content).hexdigest(),
        "case_order": [fixtures[0].case_id, fixtures[1].case_id],
    }

    output_dir = tmp_path / "resume_rollback_pair"
    output_dir.mkdir()

    case_0_off = CaseEvaluationResult(
        case_id=fixtures[0].case_id,
        status="completed",
        true_positives=1,
        usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    )
    case_0_on = CaseEvaluationResult(
        case_id=fixtures[0].case_id,
        status="completed",
        true_positives=1,
        usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    )
    # Trailing pair has case 1 off completed, but on exhausted
    case_1_off = CaseEvaluationResult(
        case_id=fixtures[1].case_id,
        status="completed",
        usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    )
    case_1_on = CaseEvaluationResult(
        case_id=fixtures[1].case_id,
        status="budget_exhausted",
        error="Quota exhausted",
        usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    )

    tracker = BudgetTracker(ExecutionBudget(max_requests=40, max_total_tokens=100000))
    tracker.requests_made = 4
    tracker.usage = TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)

    checkpoint_outcomes = [
        ArmOutcome("off", (case_0_off, case_1_off), None),
        ArmOutcome("on", (case_0_on, case_1_on), None),
    ]
    write_checkpoint(output_dir / "results.json", manifest_subset, model_spec, checkpoint_outcomes, tracker, is_simulated=True)

    provider = FakeProvider()
    outcomes = run_goal27_campaign(
        provider,
        output_dir,
        manifest_subset,
        resume=True,
        is_simulated=True,
    )

    # After rollback and resume in fake provider, both cases should now be completed
    assert [c.status for c in outcomes[0].cases] == ["completed", "completed"]
    assert [c.status for c in outcomes[1].cases] == ["completed", "completed"]
    final_json = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    assert final_json["comparative_metrics"]["complete_pair_ids"] == [fixtures[0].case_id, fixtures[1].case_id]


def test_token_accounting_strictly_separates_confirmed_and_rejected(tmp_path: Path) -> None:
    manifest = load_manifest()
    report_file = tmp_path / "GOAL27_REPORT.md"

    case_ok = CaseEvaluationResult(
        case_id="case-1",
        status="completed",
        usage=TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500, is_estimated=False),
        true_positives=1,
    )
    case_fail = CaseEvaluationResult(
        case_id="case-2",
        status="budget_exhausted",
        error="Daily API request quota (RPD) exhausted",
        usage=TokenUsage(prompt_tokens=1200, completion_tokens=4000, total_tokens=5200, is_estimated=True),
    )

    outcomes = (
        ArmOutcome("off", (case_ok, case_fail), None),
        ArmOutcome("on", (case_ok, case_fail), None),
    )

    report_text = build_readiness_report(manifest, outcomes, report_file, is_simulated=False)
    assert "**Confirmed Actual Consumption**" in report_text
    assert "**Estimated / Rejected Attempts**" in report_text
    assert "**Total Tracked Against Budget Ceiling**" in report_text
    # 2 completed cases * 1500 = 3000 confirmed tokens
    assert "| **Confirmed Actual Consumption** | 2000 | 1000 | **3000** |" in report_text
    # 2 rejected attempts * 5200 = 10400 estimated/reserved tokens
    assert "| **Estimated / Rejected Attempts** | 2400 | 8000 | **10400** |" in report_text


def test_quota_guard_preflight_blocks_execution_when_rpd_exhausted(tmp_path: Path) -> None:
    manifest = load_manifest()
    output_dir = tmp_path / "quota_guard_dir"
    output_dir.mkdir()

    class QuotaExhaustedMockUsageStore:
        def get_snapshot(self, **kwargs):
            from polaris.quota.store import QuotaSnapshot
            return QuotaSnapshot(
                provider="nvidia",
                model="minimaxai/minimax-m3.1-flash",
                quota_scope="default",
                quota_enabled=True,
                database_path=":memory:",
                utc_date="2026-11-07",
                daily_reset_utc="2026-11-08T00:00:00Z",
                requests_today=20,
                succeeded_today=19,
                failed_today=1,
                rate_limited_today=0,
                uncertain_today=0,
                active_reservations_today=0,
                expired_reservations_today=0,
                configured_rpd_limit=20,
                estimated_remaining_daily_requests=0,  # 0 requests remaining!
                requests_last_60s=0,
                configured_rpm_limit=None,
                estimated_remaining_rpm=None,
                input_tokens_last_60s=0,
                configured_tpm_limit=None,
                estimated_remaining_tpm=None,
                input_tokens_today=20000,
                output_tokens_today=10000,
                total_tokens_today=30000,
                token_accounting_source="provider_confirmed",
                is_locally_estimated=False,
            )

    provider = FakeProvider(model_name="minimaxai/minimax-m3.1-flash")
    provider.usage_store = QuotaExhaustedMockUsageStore()

    outcomes = run_goal27_campaign(
        provider,
        output_dir,
        manifest,
        is_simulated=True,
    )

    # Quota guard must block before evaluating any cases
    assert len(outcomes[0].cases) == 0
    assert len(outcomes[1].cases) == 0
    assert "quota_daily_limit_reached" in (outcomes[0].stopped_reason or "")
    assert "resets at 2026-11-08T00:00:00Z" in (outcomes[0].stopped_reason or "")
