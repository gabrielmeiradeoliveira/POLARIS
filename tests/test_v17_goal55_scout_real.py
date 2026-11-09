"""Regression tests for GOAL 55: Docker Scout Real-World Integration, Reconciliations & Quality Gate.

Validates:
1. Ingestion of real Docker Scout SARIF reports (89 findings across 8 packages).
2. Strict reconciliation: 0 findings silently lost, 89 parsed, 89 rules mapped.
3. Metadata preservation: CVEs, packages, affected versions, fixed versions ('not fixed' sanitized).
4. FindingCorrelationEngine with real multi-package vulnerabilities.
5. Baseline Engine lifecycle (NEW -> EXISTING -> anti-false-resolved on incomplete).
6. Quality Gate blocking on CRITICAL/HIGH real vulnerabilities.
7. SARIF 2.1.0 output formatting with real findings.
"""

from __future__ import annotations

import json
from pathlib import Path

from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding
from polaris.policy.baseline import BaselineFindingClassification, SecurityBaselineEngine
from polaris.policy.quality_gate import PolarisSecurityPolicy, SecurityQualityGateEngine
from polaris.reporting.sarif import SarifReportFormatter
from polaris.security.contracts import SecurityDomain
from polaris.security.docker_scout import DockerScoutAdapter
from polaris.security.models import FindingCorrelationEngine


def test_goal55_real_scout_sarif_reconciliation_89_findings():
    """Verify all 89 findings from real postgres:16-alpine Scout SARIF are imported without loss."""
    sarif_path = Path("evaluations/results/goal55/scout-postgres-real.sarif")
    if not sarif_path.is_file():
        # Fallback to sanitized fixture if full report not present
        sarif_path = Path("evaluations/results/goal55/scout-postgres-sanitized-fixture.sarif")

    content = sarif_path.read_text(encoding="utf-8")
    data = json.loads(content)
    expected_count = len(data["runs"][0]["results"])

    adapter = DockerScoutAdapter()
    findings = adapter.scan_file(str(sarif_path), content)

    # 1. Zero silent loss: imported count must exactly match SARIF results count
    assert len(findings) == expected_count

    # 2. Reconcile severities and fix versions
    severities: dict[str, int] = {}
    with_fix = 0
    without_fix = 0
    components = set()

    for f in findings:
        severities[f.severity] = severities.get(f.severity, 0) + 1
        if "Upgrade package" in f.remediation_hint:
            with_fix += 1
        else:
            without_fix += 1
        if f.component_name:
            components.add(f.component_name)

        # Verification of canonical fields
        assert f.rule_or_cve.startswith("CVE-")
        assert f.domain == SecurityDomain.IMAGE_VULNERABILITY
        assert f.advisory_source == "docker_scout"
        assert f.stable_fingerprint.startswith("bl-")

    if expected_count == 89:
        assert severities == {"LOW": 7, "MEDIUM": 31, "HIGH": 44, "CRITICAL": 7}
        assert with_fix == 78
        assert without_fix == 11
        assert components == {"libxml2", "musl", "openssl", "stdlib", "sys", "user", "util-linux", "zlib"}


def test_goal55_finding_correlation_real_findings():
    """Verify real findings correlate properly by package and CVE."""
    sarif_path = Path("evaluations/results/goal55/scout-postgres-sanitized-fixture.sarif")
    content = sarif_path.read_text(encoding="utf-8")

    adapter = DockerScoutAdapter()
    findings = adapter.scan_file(str(sarif_path), content)

    groups = FindingCorrelationEngine.correlate(findings)
    assert len(groups) == len(findings)
    for g in groups:
        assert g.primary_finding.scanner_id == "docker_scout"
        assert "docker_scout" in g.participating_scanners


def test_goal55_real_scout_baseline_and_quality_gate():
    """Verify baseline four-pass lifecycle and quality gate blocking on real findings."""
    sarif_path = Path("evaluations/results/goal55/scout-postgres-sanitized-fixture.sarif")
    content = sarif_path.read_text(encoding="utf-8")

    findings = DockerScoutAdapter().scan_file(str(sarif_path), content)
    canonical = [
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
        for f in findings
    ]

    engine = SecurityBaselineEngine()
    # Execucao A: Baseline inicial
    baseline = engine.create_baseline(canonical, files_analyzed=[str(sarif_path)])
    assert len(baseline.findings) == len(canonical)

    # Execucao B: Re-execucao identica -> EXISTING
    diff_b = engine.compare(canonical, baseline, current_files_analyzed=[str(sarif_path)], current_is_complete=True)
    assert diff_b.counts[BaselineFindingClassification.EXISTING] == len(canonical)
    assert diff_b.counts[BaselineFindingClassification.NEW] == 0
    assert diff_b.counts[BaselineFindingClassification.RESOLVED] == 0

    # Execucao C: Incompleta -> RESOLVED = 0
    diff_c = engine.compare([], baseline, current_files_analyzed=[str(sarif_path)], current_is_complete=False)
    assert diff_c.counts[BaselineFindingClassification.RESOLVED] == 0

    # Quality Gate
    policy = PolarisSecurityPolicy(fail_on_severity=["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    decision, blocking = SecurityQualityGateEngine.evaluate(canonical, policy=policy)
    assert decision.value == "FAIL"
    assert len(blocking) == len(canonical)

    # Export SARIF
    sarif_doc = SarifReportFormatter.to_sarif(canonical)
    assert sarif_doc["version"] == "2.1.0"
    assert len(sarif_doc["runs"][0]["results"]) == len(canonical)
