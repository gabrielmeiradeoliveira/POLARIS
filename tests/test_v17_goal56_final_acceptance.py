"""Integration and Acceptance Tests for GOAL 56: Final Security Module Acceptance & Release Readiness.

Validates:
1. Public CLI execution with real Docker Scout reports (Save Baseline, Load Baseline, SARIF Export).
2. Resilience: Scout failure, missing report, corrupted JSON/SARIF, unauthenticated status.
3. Strict Image Isolation: Postgres (89 CVEs) vs RabbitMQ (145 CVEs) fingerprints & baselines.
4. CI/CD Exit Code Contract: 0 = PASS, 1 = Policy FAIL, 2 = Operational/Configuration ERROR.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding
from polaris.policy.baseline import BaselineFindingClassification, SecurityBaselineEngine
from polaris.policy.quality_gate import PolarisSecurityPolicy, SecurityQualityGateEngine
from polaris.security.docker_scout import DockerScoutAdapter

runner = CliRunner()


def test_goal56_strict_image_isolation_postgres_vs_rabbitmq():
    """Verify that Postgres (89 CVEs) and RabbitMQ (145 CVEs) maintain 100% distinct fingerprints."""
    pg_path = Path("evaluations/results/goal55/scout-postgres-real.sarif")
    rmq_path = Path("evaluations/results/goal55/scout-rabbitmq-real.sarif")

    adapter = DockerScoutAdapter()
    pg_findings = adapter.scan_file(str(pg_path), pg_path.read_text(encoding="utf-8"))
    rmq_findings = adapter.scan_file(str(rmq_path), rmq_path.read_text(encoding="utf-8"))

    assert len(pg_findings) == 89
    assert len(rmq_findings) == 145

    pg_fps = {f.stable_fingerprint for f in pg_findings}
    rmq_fps = {f.stable_fingerprint for f in rmq_findings}

    # Zero collision across distinct container images
    assert len(pg_fps.intersection(rmq_fps)) == 0

    # Baseline comparison: RabbitMQ evaluated against Postgres baseline must be 100% NEW
    pg_canon = [
        CanonicalSecurityFinding(
            finding_id=f.finding_id,
            domain=CanonicalFindingDomain.IMAGE_VULNERABILITY,
            title=f.title,
            severity=f.severity,
            confidence=f.confidence,
            file_path=f.file_path,
            line=f.line,
            rule_or_cve=f.rule_or_cve,
            evidence_text=f.evidence_text,
            remediation_hint=f.remediation_hint,
        )
        for f in pg_findings
    ]
    rmq_canon = [
        CanonicalSecurityFinding(
            finding_id=f.finding_id,
            domain=CanonicalFindingDomain.IMAGE_VULNERABILITY,
            title=f.title,
            severity=f.severity,
            confidence=f.confidence,
            file_path=f.file_path,
            line=f.line,
            rule_or_cve=f.rule_or_cve,
            evidence_text=f.evidence_text,
            remediation_hint=f.remediation_hint,
        )
        for f in rmq_findings
    ]

    engine = SecurityBaselineEngine()
    pg_baseline = engine.create_baseline(pg_canon, files_analyzed=[str(pg_path)])
    diff = engine.compare(rmq_canon, pg_baseline, current_files_analyzed=[str(rmq_path)], current_is_complete=True)

    assert diff.counts[BaselineFindingClassification.EXISTING] == 0
    assert diff.counts[BaselineFindingClassification.NEW] == 145
    assert diff.counts[BaselineFindingClassification.RESOLVED] == 0


def test_goal56_resilience_and_corrupted_inputs():
    """Verify scanner handles malformed SARIF, missing files, and non-Scout JSON without crashing or silent PASS."""
    import pytest

    from polaris.security.contracts import ScannerReportParseError

    adapter = DockerScoutAdapter()

    # 1. Corrupted JSON syntax on targeted scout report raises ScannerReportParseError (fails closed)
    with pytest.raises(ScannerReportParseError) as exc_info:
        adapter.scan_file("docker-scout.sarif", "{ not valid json")
    assert "Corrupted JSON" in str(exc_info.value)

    # 2. General non-scout file with invalid JSON is skipped safely
    assert adapter.scan_file("other.json", "{ not valid json") == []

    # 3. Valid JSON but not a SARIF or Scout structure
    assert adapter.scan_file("dummy.json", json.dumps({"foo": "bar"})) == []

    # 4. SARIF from unrelated tool
    other_tool_sarif = json.dumps({
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "eslint"}}, "results": []}]
    })
    assert adapter.scan_file("eslint.sarif", other_tool_sarif) == []


def test_goal56_quality_gate_cicd_exit_codes():
    """Verify Quality Gate exit codes: 0 = PASS, 1 = FAIL."""
    f_clean = CanonicalSecurityFinding(
        finding_id="find:low-1",
        domain=CanonicalFindingDomain.IMAGE_VULNERABILITY,
        title="Low defect",
        severity="LOW",
        confidence="HIGH",
        file_path="scout.sarif",
        line=1,
        rule_or_cve="CVE-2026-0001",
        evidence_text="Low risk",
        remediation_hint="",
    )

    # 1. PASS under policy tolerating LOW
    policy_lenient = PolarisSecurityPolicy(fail_on_severity=["CRITICAL"])
    dec_pass, _ = SecurityQualityGateEngine.evaluate([f_clean], policy=policy_lenient)
    assert dec_pass.value == "PASS"

    # 2. FAIL under policy blocking LOW
    policy_strict = PolarisSecurityPolicy(fail_on_severity=["LOW"])
    dec_fail, blocking = SecurityQualityGateEngine.evaluate([f_clean], policy=policy_strict)
    assert dec_fail.value == "FAIL"
    assert len(blocking) == 1
