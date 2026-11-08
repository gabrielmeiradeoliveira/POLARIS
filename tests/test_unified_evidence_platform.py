"""Tests for Unified Security Evidence Platform (GOAL 33)."""

from polaris.container.scanner import DockerfileDefectType, DockerfileFinding
from polaris.evidence.platform import CanonicalFindingDomain, UnifiedEvidencePlatform
from polaris.supply_chain.scanner import (
    DiscoveredDependency,
    Ecosystem,
    MatchedVulnerability,
    VulnerabilityAdvisory,
    VulnerabilityMatchStatus,
)


def test_unified_evidence_platform_correlation():
    """Verify unification of supply chain and container findings into canonical findings."""
    dep = DiscoveredDependency.create("requests", Ecosystem.PYPI, "requirements.txt", "2.20.0")
    adv = VulnerabilityAdvisory(
        advisory_id="GHSA-1234",
        cve_id="CVE-2018-18074",
        package_name="requests",
        ecosystem=Ecosystem.PYPI,
        vulnerable_versions="<2.21.0",
        fixed_version="2.21.0",
        severity="HIGH",
    )
    m = MatchedVulnerability(
        dependency=dep,
        advisory=adv,
        status=VulnerabilityMatchStatus.CONFIRMED_AFFECTED,
        evidence="Vulnerable version",
    )

    df_finding = DockerfileFinding(
        defect_type=DockerfileDefectType.ROOT_USER_EXECUTION,
        line=10,
        instruction="USER root",
        severity="HIGH",
        remediation="Use non-root user",
    )

    canonical = UnifiedEvidencePlatform.correlate_findings([], [m], [df_finding])
    assert len(canonical) == 2

    domains = {c.domain for c in canonical}
    assert CanonicalFindingDomain.SUPPLY_CHAIN in domains
    assert CanonicalFindingDomain.CONTAINER in domains
    assert canonical[0].finding_id.startswith("find:")
