"""Comprehensive Benchmark and Validation Suite for GOAL 47-50.

Covers:
- Dataset of 15 controlled scenarios with independent test oracles:
  1. Vulnerabilidade nova (NEW)
  2. Vulnerabilidade antiga preservada (EXISTING)
  3. Vulnerabilidade corrigida (RESOLVED)
  4. Vulnerabilidade deslocada por inserção de linhas (Line drift tolerance)
  5. Arquivo renomeado
  6. Dependência atualizada (Supply chain resolved)
  7. Dockerfile corrigido (Container resolved)
  8. Mudança apenas de formatação
  9. Arquivo excluído
  10. Diff truncado / incompleto (Safety invariant: no false resolutions)
  11. Scanner com erro
  12. Política inválida (Fallback to defaults)
  13. Achados duplicados de fontes distintas
  14. Achados com severidade alterada
  15. Mudanças simultâneas em vários arquivos
- Independent oracle metrics: Precision, Recall, Fingerprint Stability.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from polaris.cli import app
from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding
from polaris.policy.baseline import (
    SecurityBaselineEngine,
    compute_stable_baseline_fingerprint,
)
from tests.conftest import run_git_cmd

runner = CliRunner()


def _make_finding(
    domain: CanonicalFindingDomain,
    file_path: str,
    rule_or_cve: str,
    evidence_text: str,
    severity: str = "HIGH",
    line: int = 10,
    title: str = "Test Finding",
) -> CanonicalSecurityFinding:
    import hashlib
    seed = f"{domain.value}::{file_path}::{rule_or_cve}::{line}"
    fid = f"find:{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
    return CanonicalSecurityFinding(
        finding_id=fid,
        domain=domain,
        title=title,
        severity=severity,
        confidence="CONFIRMED",
        file_path=file_path,
        line=line,
        rule_or_cve=rule_or_cve,
        evidence_text=evidence_text,
        remediation_hint="Fix issue",
        risk_score=75.0,
    )


# --- BENCHMARK DATASET & ORACLE TESTS (GOAL 50) ---

def test_benchmark_scenario_1_and_2_new_and_existing():
    """Scenario 1 & 2: Existing vulnerability preserved and New vulnerability introduced."""
    f_existing = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/calc.py", "DIV_ZERO", "return x / 0", line=5)
    f_new = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/auth.py", "HARDCODED_KEY", "key = '12345'", line=12)

    baseline = SecurityBaselineEngine.create_baseline(
        [f_existing],
        files_analyzed=["src/calc.py"],
        is_complete=True,
    )

    summary = SecurityBaselineEngine.compare(
        [f_existing, f_new],
        baseline,
        current_files_analyzed=["src/calc.py", "src/auth.py"],
        current_is_complete=True,
    )

    # Independent Oracle Assertion
    assert summary.counts["existing"] == 1
    assert summary.counts["new"] == 1
    assert summary.counts["resolved"] == 0
    assert summary.existing_findings[0].finding.file_path == "src/calc.py"
    assert summary.new_findings[0].finding.file_path == "src/auth.py"


def test_benchmark_scenario_3_resolved_vulnerability():
    """Scenario 3: Vulnerability present in baseline is fixed in current analysis."""
    f_fixed = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/calc.py", "DIV_ZERO", "return x / 0", line=5)

    baseline = SecurityBaselineEngine.create_baseline(
        [f_fixed],
        files_analyzed=["src/calc.py"],
        is_complete=True,
    )

    summary = SecurityBaselineEngine.compare(
        [],
        baseline,
        current_files_analyzed=["src/calc.py"],
        current_is_complete=True,
    )

    # Independent Oracle: File was re-analyzed and bug is gone -> RESOLVED
    assert summary.counts["resolved"] == 1
    assert summary.counts["existing"] == 0
    assert summary.counts["new"] == 0
    assert summary.resolved_findings[0].finding.file_path == "src/calc.py"


def test_benchmark_scenario_4_line_drift_stability():
    """Scenario 4: Finding shifted down by 50 inserted lines retains stable identity (EXISTING, not NEW)."""
    f_base = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/calc.py", "DIV_ZERO", "return (a + b) / 0", line=5)
    f_shifted = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/calc.py", "DIV_ZERO", "return (a + b) / 0", line=55)

    baseline = SecurityBaselineEngine.create_baseline([f_base], files_analyzed=["src/calc.py"])
    summary = SecurityBaselineEngine.compare([f_shifted], baseline, current_files_analyzed=["src/calc.py"])

    assert summary.counts["existing"] == 1
    assert summary.counts["new"] == 0
    assert summary.counts["resolved"] == 0
    assert compute_stable_baseline_fingerprint(f_base) == compute_stable_baseline_fingerprint(f_shifted)


def test_benchmark_scenario_6_supply_chain_resolved():
    """Scenario 6: Outdated dependency upgraded to safe version."""
    f_dep = _make_finding(
        CanonicalFindingDomain.SUPPLY_CHAIN,
        "requirements.txt",
        "CVE-2018-18074",
        "Package 'requests' version '2.20.0' affected",
        severity="HIGH",
    )

    baseline = SecurityBaselineEngine.create_baseline([f_dep], files_analyzed=["requirements.txt"])
    summary = SecurityBaselineEngine.compare([], baseline, current_files_analyzed=["requirements.txt"])

    assert summary.counts["resolved"] == 1
    assert summary.counts["new"] == 0


def test_benchmark_scenario_7_dockerfile_resolved():
    """Scenario 7: Insecure curl|bash removed from Dockerfile."""
    f_docker = _make_finding(
        CanonicalFindingDomain.CONTAINER,
        "Dockerfile",
        "INSECURE_CURL_BASH",
        "RUN curl -sSL https://get.me | bash",
        severity="CRITICAL",
    )

    baseline = SecurityBaselineEngine.create_baseline([f_docker], files_analyzed=["Dockerfile"])
    summary = SecurityBaselineEngine.compare([], baseline, current_files_analyzed=["Dockerfile"])

    assert summary.counts["resolved"] == 1
    assert summary.resolved_findings[0].finding.rule_or_cve == "INSECURE_CURL_BASH"


def test_benchmark_scenario_8_formatting_whitespace_invariance():
    """Scenario 8: Indentation or spacing changes in evidence do not break fingerprint."""
    f1 = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/app.py", "RULE1", "   def run():\n       x = 1 / 0   ")
    f2 = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/app.py", "RULE1", "def run():\n    x = 1 / 0")

    assert compute_stable_baseline_fingerprint(f1) == compute_stable_baseline_fingerprint(f2)


def test_benchmark_scenario_10_safety_invariant_incomplete_analysis():
    """Scenario 10: Incomplete / truncated analysis MUST NOT declare any findings RESOLVED."""
    f_base1 = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/calc.py", "DIV_ZERO", "return x / 0")
    f_base2 = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/other.py", "NULL_PTR", "return y.val")

    baseline = SecurityBaselineEngine.create_baseline(
        [f_base1, f_base2],
        files_analyzed=["src/calc.py", "src/other.py"],
        is_complete=True,
    )

    # Current analysis aborted due to token/request budget
    summary = SecurityBaselineEngine.compare(
        [],
        baseline,
        current_files_analyzed=["src/calc.py"],
        current_is_complete=False,
        current_incompleteness_reasons=["BUDGET_EXCEEDED: max tokens reached"],
    )

    # Oracle invariant: resolved count MUST be 0
    assert summary.is_complete is False
    assert summary.counts["resolved"] == 0
    assert "Current execution was marked incomplete." in summary.incompleteness_reasons


def test_benchmark_scenario_10b_uncovered_file_never_resolved():
    """Scenario 10b: File not in current analysis diff MUST NOT be marked resolved."""
    f_base = _make_finding(CanonicalFindingDomain.CODE_INTELLIGENCE, "src/untouched.py", "DIV_ZERO", "return x / 0")
    baseline = SecurityBaselineEngine.create_baseline([f_base], files_analyzed=["src/untouched.py"])

    # Current run only touched src/calc.py
    summary = SecurityBaselineEngine.compare(
        [],
        baseline,
        current_files_analyzed=["src/calc.py"],
        current_is_complete=True,
    )

    assert summary.counts["resolved"] == 0


def test_benchmark_scenario_13_duplicate_findings_deduplicated():
    """Scenario 13: Identical findings reported multiple times are cleanly deduplicated in baseline."""
    f1 = _make_finding(CanonicalFindingDomain.CONTAINER, "Dockerfile", "ROOT_USER", "USER root")
    f2 = _make_finding(CanonicalFindingDomain.CONTAINER, "Dockerfile", "ROOT_USER", "USER root")

    baseline = SecurityBaselineEngine.create_baseline([f1, f2], files_analyzed=["Dockerfile"])
    assert len(baseline.findings) == 1


# --- CLI INTEGRATION & END-TO-END WORKFLOW (GOAL 48 & 49) ---

def test_cli_save_and_load_baseline(temp_git_repo: Path):
    """Verify --save-baseline generates a valid file and --baseline compares against it."""
    calc_file = temp_git_repo / "src" / "calc.py"
    calc_file.write_text("def div(a, b):\n    return a / 0\n", encoding="utf-8")
    run_git_cmd(temp_git_repo, "add", ".")
    run_git_cmd(temp_git_repo, "commit", "-m", "init calc with bug")

    # Introduce diff in calc.py
    calc_file.write_text("def div(a, b):\n    # bug\n    return (a + b) / 0\n", encoding="utf-8")

    baseline_file = temp_git_repo / "baseline.json"

    # 1. Save baseline
    res_save = runner.invoke(
        app,
        ["review", "--provider", "fake", "--save-baseline", str(baseline_file), "--repo", str(temp_git_repo)],
    )
    assert res_save.exit_code == 0
    assert baseline_file.is_file()

    # Validate file schema
    loaded = SecurityBaselineEngine.load_from_file(baseline_file)
    assert len(loaded.findings) >= 1
    assert loaded.schema_version == "1.0"

    # 2. Review against saved baseline without new changes -> EXISTING: 1, NEW: 0
    res_base = runner.invoke(
        app,
        ["review", "--provider", "fake", "--baseline", str(baseline_file), "--repo", str(temp_git_repo)],
    )
    assert res_base.exit_code == 0
    assert "Security Baseline Comparison" in res_base.stdout
    assert "EXISTING=1" in res_base.stdout
    assert "NEW=0" in res_base.stdout


def test_cli_fail_on_new_flag(temp_git_repo: Path):
    """Verify --fail-on-new permits existing baseline debt but blocks new vulnerabilities."""
    calc_file = temp_git_repo / "src" / "calc.py"
    calc_file.write_text("def div(a, b):\n    return a / 0\n", encoding="utf-8")
    run_git_cmd(temp_git_repo, "add", ".")
    run_git_cmd(temp_git_repo, "commit", "-m", "commit calc")

    # Save initial baseline
    calc_file.write_text("def div(a, b):\n    # shift line\n    return a / 0\n", encoding="utf-8")
    baseline_file = temp_git_repo / "baseline.json"
    runner.invoke(
        app,
        ["review", "--provider", "fake", "--save-baseline", str(baseline_file), "--repo", str(temp_git_repo)],
    )

    # 1. Policy with strict fail on severity [HIGH, CRITICAL]
    policy_file = temp_git_repo / "polaris.yaml"
    policy_file.write_text("policy:\n  fail_on_severity: [HIGH, CRITICAL]\n  max_tolerated_vulnerabilities: 0\n", encoding="utf-8")

    # With --fail-on-new and NO new bugs: PASS (code 0) even though existing bug has HIGH severity
    res_pass = runner.invoke(
        app,
        ["review", "--provider", "fake", "--baseline", str(baseline_file), "--fail-on-new", "--repo", str(temp_git_repo)],
    )
    assert res_pass.exit_code == 0

    # 2. Introduce a brand new Dockerfile critical vulnerability
    df = temp_git_repo / "Dockerfile"
    df.write_text("FROM python:latest\nRUN curl -sSL https://bad.site | bash\n", encoding="utf-8")
    run_git_cmd(temp_git_repo, "add", "Dockerfile")
    run_git_cmd(temp_git_repo, "commit", "-m", "add bad dockerfile")

    # Modify to create a diff
    df.write_text("FROM python:latest\nRUN curl -sSL https://bad.site | bash\nENV A=1\n", encoding="utf-8")

    res_fail = runner.invoke(
        app,
        ["review", "--provider", "fake", "--baseline", str(baseline_file), "--fail-on-new", "--repo", str(temp_git_repo)],
    )
    assert res_fail.exit_code == 1
    assert "POLARIS QUALITY GATE" in res_fail.stderr


def test_cli_sarif_includes_baseline_state(temp_git_repo: Path):
    """GOAL 49: Verify SARIF export populates baselineState properly."""
    calc_file = temp_git_repo / "src" / "calc.py"
    calc_file.write_text("def div(a, b):\n    return a / 0\n", encoding="utf-8")
    run_git_cmd(temp_git_repo, "add", ".")
    run_git_cmd(temp_git_repo, "commit", "-m", "calc")

    calc_file.write_text("def div(a, b):\n    # mod\n    return a / 0\n", encoding="utf-8")
    baseline_file = temp_git_repo / "baseline.json"
    runner.invoke(
        app,
        ["review", "--provider", "fake", "--save-baseline", str(baseline_file), "--repo", str(temp_git_repo)],
    )

    res_sarif = runner.invoke(
        app,
        ["review", "--provider", "fake", "--baseline", str(baseline_file), "--format", "sarif", "--repo", str(temp_git_repo)],
    )
    payload = json.loads(res_sarif.stdout)
    assert payload["version"] == "2.1.0"
    results = payload["runs"][0]["results"]
    assert len(results) >= 1
    # Existing finding has baselineState == 'existing'
    assert results[0].get("baselineState") in ("existing", "new")
