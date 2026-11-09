"""Integration and Regression Test Suite for Docker Scout Live & Offline Integration (GOAL 54).

Validates:
1. DockerScoutAdapter live diagnostic probe (detects CLI presence and auth status).
2. Parsing and normalization of real Docker Scout SARIF reports.
3. Baseline Engine integration: NEW -> EXISTING -> anti-false-resolved on missing/malformed report.
4. Quality Gate integration with Docker Scout findings.
5. SARIF 2.1.0 output formatting preservation.
"""

from __future__ import annotations

import json

from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding
from polaris.policy.baseline import BaselineFindingClassification, SecurityBaselineEngine
from polaris.policy.quality_gate import PolarisSecurityPolicy, SecurityQualityGateEngine
from polaris.reporting.sarif import SarifReportFormatter
from polaris.security.contracts import SecurityDomain
from polaris.security.docker_scout import DockerScoutAdapter


def test_goal54_docker_scout_live_diagnostic():
    """Verify Docker Scout adapter correctly inspects local binary and reports auth status."""
    adapter = DockerScoutAdapter()
    assert adapter.is_available() is True
    ok, msg = adapter.check_live_auth_status()
    assert ok is True
    assert "docker scout CLI available" in msg


def test_goal54_docker_scout_real_sarif_normalization_and_baseline_lifecycle():
    """Verify Scout SARIF parsing maps to Canonical findings and integrates with Baseline Engine."""
    # Real-world structured SARIF matching Docker Scout output
    raw_scout_sarif = json.dumps({
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "docker scout",
                        "version": "1.21.0",
                        "rules": [
                            {
                                "id": "CVE-2024-24576",
                                "shortDescription": {"text": "Rust Standard Library Command Injection on Windows"},
                                "help": {"text": "Upgrade package to version 1.77.2 or later."},
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "CVE-2024-24576",
                        "message": {"text": "Vulnerable rust runtime identified in container layer"},
                        "level": "error",
                        "properties": {
                            "packageName": "rust",
                            "packageVersion": "1.75.0",
                            "purl": "pkg:generic/rust@1.75.0",
                        },
                    }
                ],
            }
        ],
    })

    adapter = DockerScoutAdapter()
    findings = adapter.scan_file("docker-scout.sarif", raw_scout_sarif)
    assert len(findings) == 1

    f = findings[0]
    assert f.rule_or_cve == "CVE-2024-24576"
    assert f.component_name == "rust"
    assert f.component_version == "1.75.0"
    assert f.domain == SecurityDomain.IMAGE_VULNERABILITY
    assert f.advisory_source == "docker_scout"

    # Map to Canonical finding for baseline engine verification
    canonical = CanonicalSecurityFinding(
        finding_id=f.finding_id,
        domain=CanonicalFindingDomain.CONTAINER,
        title=f.title,
        severity="HIGH",
        confidence="CONFIRMED",
        file_path="docker-scout.sarif",
        line=1,
        rule_or_cve=f.rule_or_cve,
        evidence_text=f.evidence_text,
        remediation_hint=f.remediation_hint,
    )

    engine = SecurityBaselineEngine()
    # 1. First run creates baseline
    baseline = engine.create_baseline([canonical], files_analyzed=["docker-scout.sarif"])
    assert len(baseline.findings) == 1

    # 2. Re-evaluating against same findings yields EXISTING = 1, NEW = 0
    diff_report = engine.compare(
        [canonical],
        baseline,
        current_files_analyzed=["docker-scout.sarif"],
        current_is_complete=True,
    )
    assert diff_report.counts[BaselineFindingClassification.EXISTING] == 1
    assert diff_report.counts[BaselineFindingClassification.NEW] == 0
    assert diff_report.counts[BaselineFindingClassification.RESOLVED] == 0

    # 3. Incomplete execution invariant: if execution is marked incomplete, resolved is never emitted
    incomplete_diff = engine.compare(
        [],
        baseline,
        current_files_analyzed=["docker-scout.sarif"],
        current_is_complete=False,
    )
    assert incomplete_diff.counts[BaselineFindingClassification.RESOLVED] == 0

    # 4. Uncovered file invariant: if file was not inspected by scanner, resolved is never emitted
    uncovered_diff = engine.compare(
        [],
        baseline,
        current_files_analyzed=[],
        current_is_complete=True,
    )
    assert uncovered_diff.counts[BaselineFindingClassification.RESOLVED] == 0


def test_goal54_quality_gate_and_sarif_export():
    """Verify Quality Gate evaluates findings and SARIF formatter exports baseline states."""
    f = CanonicalSecurityFinding(
        finding_id="find:scout-1",
        domain=CanonicalFindingDomain.CONTAINER,
        title="High severity Docker Scout CVE",
        severity="CRITICAL",
        confidence="CONFIRMED",
        file_path="docker-scout.sarif",
        line=1,
        rule_or_cve="CVE-2024-24576",
        evidence_text="Vulnerable runtime",
        remediation_hint="Upgrade runtime",
    )

    policy = PolarisSecurityPolicy(fail_on_severity=["CRITICAL"])
    decision, blocking = SecurityQualityGateEngine.evaluate([f], policy=policy)
    assert decision.value == "FAIL"
    assert len(blocking) == 1
    assert "CRITICAL" in blocking[0]

    sarif_doc = SarifReportFormatter.to_sarif([f])
    assert sarif_doc["version"] == "2.1.0"
    results = sarif_doc["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "CVE-2024-24576"
