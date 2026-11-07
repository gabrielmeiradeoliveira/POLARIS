"""Unit and integration tests for Polaris Quality Engine, Quality Gate, and PR Baseline comparison."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from polaris.core.models import (
    AnalysisReport,
    AnalysisWarning,
    Confidence,
    Finding,
    FindingCategory,
    LineRange,
    ProviderInfo,
    Severity,
    TokenUsage,
)
from polaris.quality import (
    QUALITY_FORMULA_VERSION,
    QUALITY_GATE_VERSION,
    FindingDeltaClassification,
    OperationalStatus,
    QualityGateStatus,
    QualityGrade,
    build_github_check_contract,
    compare_pull_request,
    compute_stable_finding_fingerprint,
    evaluate_quality,
)
from polaris.web.api import create_app
from polaris.web.store import WebStore
from polaris.web.worker import StaticAnalysisWorker


class InlineWorker:
    def __init__(self, store: WebStore) -> None:
        self.worker = StaticAnalysisWorker(store)

    def start(self, job_id: str) -> None:
        self.worker.run_inline(job_id)


def _make_finding(
    finding_id: str,
    *,
    severity: Severity = Severity.MEDIUM,
    confidence: Confidence = Confidence.HIGH,
    category: FindingCategory = FindingCategory.LOGIC_ERROR,
    file_path: str = "src/service.py",
    start_line: int = 10,
    end_line: int | None = None,
    title: str = "Synthetic logic issue",
    description: str = "Synthetic description explaining the runtime failure.",
    evidence: str = "if status is 'ready':",
) -> Finding:
    return Finding(
        id=finding_id,
        module_id="code_review",
        category=category,
        severity=severity,
        confidence=confidence,
        file_path=file_path,
        line_range=LineRange(start_line=start_line, end_line=end_line or start_line),
        title=title,
        description=description,
        evidence=evidence,
        suggested_remediation="Use '==' for literal comparison.",
    )


def _make_report(
    findings: list[Finding] | None = None,
    *,
    status: str = "completed",
    files_analyzed: list[str] | None = None,
    warnings: list[AnalysisWarning] | None = None,
    modules_executed: list[str] | None = None,
) -> AnalysisReport:
    return AnalysisReport(
        repository_root="/repo",
        target_description="synthetic test scope",
        modules_executed=["code_review"] if modules_executed is None else modules_executed,
        provider=ProviderInfo(provider_name="fake", model_name="fake-v1"),
        usage=TokenUsage(),
        files_analyzed=["src/service.py"] if files_analyzed is None else files_analyzed,
        findings=findings or [],
        warnings=warnings or [],
        status=status,  # type: ignore[arg-type]
    )


def test_quality_engine_grade_boundaries_a_b_c_d_f() -> None:
    # Grade A: 0 findings -> 100.0
    eval_a_clean = evaluate_quality(_make_report([]))
    assert eval_a_clean.grade == QualityGrade.A
    assert eval_a_clean.score == 100.0
    assert eval_a_clean.formula_version == QUALITY_FORMULA_VERSION

    # Grade A boundary: 1 MEDIUM (HIGH confidence) -> penalty 10.0 -> score 90.0 -> Grade A
    eval_a_edge = evaluate_quality(_make_report([_make_finding("dcd-a1", severity=Severity.MEDIUM)]))
    assert eval_a_edge.grade == QualityGrade.A
    assert eval_a_edge.score == 90.0

    # Grade B boundary via score: 1 MEDIUM + 1 LOW -> penalty 14.0 -> score 86.0 -> Grade B
    eval_b_score = evaluate_quality(
        _make_report(
            [
                _make_finding("dcd-b1", severity=Severity.MEDIUM, start_line=10),
                _make_finding("dcd-b2", severity=Severity.LOW, start_line=20, evidence="x = 1"),
            ]
        )
    )
    assert eval_b_score.grade == QualityGrade.B
    assert eval_b_score.score == 86.0

    # Grade B boundary via HIGH severity cap: 1 HIGH (LOW confidence = 11.0 penalty -> score 89.0, or even if score >= 90)
    eval_b_high = evaluate_quality(_make_report([_make_finding("dcd-b3", severity=Severity.HIGH)]))
    assert eval_b_high.grade == QualityGrade.B
    assert eval_b_high.score == 78.0

    # Grade C boundary: 3 MEDIUM -> penalty 30.0 -> score 70.0 -> Grade C
    eval_c = evaluate_quality(
        _make_report(
            [
                _make_finding("dcd-c1", severity=Severity.MEDIUM, start_line=10),
                _make_finding("dcd-c2", severity=Severity.MEDIUM, start_line=20),
                _make_finding("dcd-c3", severity=Severity.MEDIUM, start_line=30),
            ]
        )
    )
    assert eval_c.grade == QualityGrade.C
    assert eval_c.score == 70.0

    # Grade D boundary: 2 HIGH + 1 LOW -> penalty 48.0 -> score 52.0 -> Grade D
    eval_d = evaluate_quality(
        _make_report(
            [
                _make_finding("dcd-d1", severity=Severity.HIGH, start_line=10),
                _make_finding("dcd-d2", severity=Severity.HIGH, start_line=20),
                _make_finding("dcd-d3", severity=Severity.LOW, start_line=30),
            ]
        )
    )
    assert eval_d.grade == QualityGrade.D
    assert eval_d.score == 52.0

    # Grade F via CRITICAL finding (even with single finding, score 55.0 -> capped at F)
    eval_f_crit = evaluate_quality(
        _make_report(
            [
                _make_finding(
                    "dcd-f1",
                    severity=Severity.CRITICAL,
                    category=FindingCategory.CORRECTNESS,
                    evidence="return total / 0",
                )
            ]
        )
    )
    assert eval_f_crit.grade == QualityGrade.F
    assert eval_f_crit.score == 55.0
    assert len(eval_f_crit.evidence_used) == 1
    assert eval_f_crit.evidence_used[0].effective_penalty == 45.0

    # Grade F via score < 40 without critical: 3 HIGH -> penalty 66.0 -> score 34.0 -> Grade F
    eval_f_score = evaluate_quality(
        _make_report(
            [
                _make_finding("dcd-f2", severity=Severity.HIGH, start_line=10),
                _make_finding("dcd-f3", severity=Severity.HIGH, start_line=20),
                _make_finding("dcd-f4", severity=Severity.HIGH, start_line=30),
            ]
        )
    )
    assert eval_f_score.grade == QualityGrade.F
    assert eval_f_score.score == 34.0


def test_quality_engine_not_rated_on_incomplete_empty_or_failed() -> None:
    # 1. Incomplete status
    eval_inc = evaluate_quality(
        _make_report(
            status="incomplete",
            warnings=[AnalysisWarning(code="DIFF_TRUNCATED", message="Diff exceeded budget")],
        )
    )
    assert eval_inc.grade == QualityGrade.NOT_RATED
    assert eval_inc.score is None
    assert eval_inc.scope.operational_status == OperationalStatus.INCOMPLETE
    assert not eval_inc.scope.is_complete
    assert "DIFF_TRUNCATED" in (eval_inc.not_rated_reason or "")

    # 2. Empty diff / zero files analyzed
    eval_empty = evaluate_quality(_make_report(status="empty_diff", files_analyzed=[]))
    assert eval_empty.grade == QualityGrade.NOT_RATED
    assert eval_empty.score is None
    assert "empty diff" in (eval_empty.not_rated_reason or "").lower()

    # 3. Failed job
    eval_failed = evaluate_quality(None, job_status="failed", job_error="Git revision not found")
    assert eval_failed.grade == QualityGrade.NOT_RATED
    assert eval_failed.score is None
    assert eval_failed.scope.operational_status == OperationalStatus.FAILED
    assert "Git revision not found" in (eval_failed.not_rated_reason or "")


def test_pr_comparison_classifies_new_existing_resolved_and_uncertain() -> None:
    existing_f_base = _make_finding(
        "dcd-exist-1",
        severity=Severity.MEDIUM,
        file_path="src/service.py",
        start_line=12,
        evidence="if state is 'active':",
    )
    # Same finding shifted down by 4 lines in PR
    existing_f_pr = _make_finding(
        "dcd-exist-2",
        severity=Severity.MEDIUM,
        file_path="src/service.py",
        start_line=16,
        evidence="if state is 'active':  # comment added",
    )
    resolved_f_base = _make_finding(
        "dcd-res-1",
        severity=Severity.LOW,
        file_path="src/service.py",
        start_line=30,
        evidence="fh = open('data.txt')",
    )
    uncertain_f_base = _make_finding(
        "dcd-unc-base",
        severity=Severity.MEDIUM,
        category=FindingCategory.BOUNDARY_CONDITION,
        file_path="src/service.py",
        start_line=50,
        title="Potential ZeroDivisionError when 'items' is empty",
        description="Dividing by len(items) without emptiness guard raises ZeroDivisionError.",
        evidence="avg = total_sum / len(items)",
    )
    # Shifted 35 lines away with partially refactored variable name but same concept & tokens
    uncertain_f_pr = _make_finding(
        "dcd-unc-pr",
        severity=Severity.MEDIUM,
        category=FindingCategory.CORRECTNESS,
        file_path="src/service.py",
        start_line=88,
        title="Division by len(items) on unguarded path",
        description="Unchecked division by len(items) when computing average.",
        evidence="weighted_avg = (total_sum * weight) / len(items)",
    )
    new_crit_pr = _make_finding(
        "dcd-new-crit",
        severity=Severity.CRITICAL,
        category=FindingCategory.CORRECTNESS,
        file_path="src/service.py",
        start_line=105,
        title="Division or modulo by zero",
        description="Divides by literal zero.",
        evidence="return ratio / 0",
    )

    assert compute_stable_finding_fingerprint(existing_f_base) == compute_stable_finding_fingerprint(existing_f_pr)

    base_report = _make_report([existing_f_base, resolved_f_base, uncertain_f_base])
    pr_report = _make_report([existing_f_pr, uncertain_f_pr, new_crit_pr])

    comp = compare_pull_request(base_report, pr_report)
    assert comp.base_evaluation.grade == QualityGrade.B  # 10 + 4 + 10 = 24 penalty -> 76.0 (Grade B)
    assert comp.pr_evaluation.grade == QualityGrade.F  # new critical finding -> Grade F
    assert comp.grade_delta == "B -> F"
    assert comp.quality_gate.status == QualityGateStatus.FAILED
    assert comp.quality_gate.gate_version == QUALITY_GATE_VERSION
    assert comp.counts == {"new": 1, "existing": 1, "resolved": 1, "uncertain": 1}
    assert comp.new_findings[0].finding.id == "dcd-new-crit"
    assert comp.existing_findings[0].Classification if hasattr(comp.existing_findings[0], "Classification") else comp.existing_findings[0].classification == FindingDeltaClassification.EXISTING
    assert comp.resolved_findings[0].finding.id == "dcd-res-1"
    assert comp.uncertain_findings[0].finding.id == "dcd-unc-pr"

    gh_contract = build_github_check_contract(comp, head_sha="abc1234")
    assert gh_contract.conclusion == "failure"
    assert len(gh_contract.annotations) == 2


def test_pr_comparison_b_to_a_clean_pr_and_incomplete_pr() -> None:
    # Base project is Grade B (has 1 existing HIGH finding), PR introduces 0 new findings -> PR Grade A, Gate PASSED
    existing_high = _make_finding(
        "dcd-base-high",
        severity=Severity.HIGH,
        category=FindingCategory.STATE_MUTATION,
        file_path="src/service.py",
        start_line=5,
        title="Mutable default argument shared across function calls",
        evidence="def append_item(val, bucket=[]):",
    )
    base_report = _make_report([existing_high])
    pr_clean_report = _make_report([existing_high])

    clean_comp = compare_pull_request(base_report, pr_clean_report)
    assert clean_comp.base_evaluation.grade == QualityGrade.B
    assert clean_comp.pr_evaluation.grade == QualityGrade.A
    assert clean_comp.quality_gate.status == QualityGateStatus.PASSED
    assert clean_comp.counts["new"] == 0
    assert clean_comp.counts["existing"] == 1

    # Incomplete PR -> NOT_RATED and gate INCONCLUSIVE
    pr_inc_report = _make_report(
        [existing_high],
        status="incomplete",
        warnings=[AnalysisWarning(code="MAX_FILES_EXCEEDED", message="Exceeded max files")],
    )
    inc_comp = compare_pull_request(base_report, pr_inc_report)
    assert inc_comp.pr_evaluation.grade == QualityGrade.NOT_RATED
    assert inc_comp.quality_gate.status == QualityGateStatus.INCONCLUSIVE
    assert not inc_comp.quality_gate.passed


def test_real_detector_b_to_f_on_synthetic_git_repository(temp_git_repo: Path, tmp_path: Path) -> None:
    """End-to-end verification that a real detector run rates base B and PR F when a critical defect is added."""
    calc_path = temp_git_repo / "src" / "calc.py"
    # Base change: has a high-severity mutable default argument -> penalty 22 -> score 78.0 -> Grade B
    calc_path.write_text(
        "def add(a: int, b: int, cache=[]) -> int:\n"
        "    cache.append(a + b)\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    store = WebStore(f"sqlite:///{tmp_path / 'polaris.sqlite3'}", initialize=True)
    client = TestClient(create_app(store.database_url, worker=InlineWorker(store), initialize=True))

    proj_res = client.post("/api/projects", json={"name": "Polaris Core", "path": str(temp_git_repo)})
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # Run baseline analysis
    base_job_res = client.post(f"/api/projects/{project_id}/analyses", json={"analysis_mode": "project"})
    assert base_job_res.status_code == 202
    base_job = client.get(f"/api/analyses/{base_job_res.json()['id']}").json()
    assert base_job["status"] == "completed"
    assert base_job["quality"]["grade"] == "B"
    assert base_job["quality"]["score"] == 78.0

    # Now introduce a critical division-by-zero bug in the PR working tree
    calc_path.write_text(
        "def add(a: int, b: int, cache=[]) -> int:\n"
        "    cache.append(a + b)\n"
        "    return (a + b) / 0\n",
        encoding="utf-8",
    )

    pr_job_res = client.post(
        f"/api/projects/{project_id}/analyses",
        json={"analysis_mode": "pr", "baseline_job_id": base_job["id"]},
    )
    assert pr_job_res.status_code == 202
    pr_job = client.get(f"/api/analyses/{pr_job_res.json()['id']}").json()
    assert pr_job["status"] == "completed"
    assert pr_job["quality"]["grade"] == "F"
    assert pr_job["quality_gate"]["status"] == "FAILED"
    assert pr_job["comparison"]["grade_delta"] == "B -> F"
    assert pr_job["comparison"]["counts"]["new"] == 1
    assert pr_job["comparison"]["counts"]["existing"] == 1
    assert any("critical" in r.lower() for r in pr_job["quality_gate"]["reasons"])
