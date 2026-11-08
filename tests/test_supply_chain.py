"""Tests for Supply Chain Security Scanner (GOAL 31)."""

from polaris.supply_chain.scanner import (
    DiscoveredDependency,
    Ecosystem,
    MatchedVulnerability,
    SupplyChainSecurityScanner,
    VulnerabilityAdvisory,
    VulnerabilityMatchStatus,
)


def test_requirements_parsing_and_matching():
    """Verify parsing of requirements.txt and matching against local vulnerability advisory."""
    req_content = """
# Production requirements
requests==2.20.0
flask>=2.0.0
django==3.1.2
"""
    deps = SupplyChainSecurityScanner.parse_manifest("requirements.txt", req_content)
    assert len(deps) == 3

    by_name = {d.name: d for d in deps}
    assert by_name["requests"].version == "2.20.0"
    assert by_name["requests"].purl == "pkg:pypi/requests@2.20.0"
    assert by_name["flask"].version is None  # Range not treated as pinned

    # Advisory database snapshot
    advisories = [
        VulnerabilityAdvisory(
            advisory_id="GHSA-w5p7-h5w8-2hfq",
            cve_id="CVE-2018-18074",
            package_name="requests",
            ecosystem=Ecosystem.PYPI,
            vulnerable_versions="<2.21.0",
            fixed_version="2.21.0",
            severity="HIGH",
        ),
        VulnerabilityAdvisory(
            advisory_id="GHSA-6767-1234-5678",
            cve_id="CVE-2021-3281",
            package_name="django",
            ecosystem=Ecosystem.PYPI,
            vulnerable_versions="<3.1.1",
            fixed_version="3.1.1",
            severity="MEDIUM",
        ),
    ]

    scanner = SupplyChainSecurityScanner(local_advisories=advisories)
    matches = scanner.match_vulnerabilities(deps)

    assert len(matches) == 2
    req_match = next(m for m in matches if m.dependency.name == "requests")
    assert req_match.status == VulnerabilityMatchStatus.CONFIRMED_AFFECTED
    assert "CVE-2018-18074" in req_match.evidence

    django_match = next(m for m in matches if m.dependency.name == "django")
    assert django_match.status == VulnerabilityMatchStatus.NOT_AFFECTED


def test_cyclonedx_sbom_generation():
    """Verify deterministic CycloneDX SBOM generation."""
    dep1 = DiscoveredDependency.create("requests", Ecosystem.PYPI, "requirements.txt", "2.20.0")
    dep2 = DiscoveredDependency.create("lodash", Ecosystem.NPM, "package.json", "4.17.21")

    sbom = SupplyChainSecurityScanner.generate_sbom([dep1, dep2])
    assert sbom["bomFormat"] == "CycloneDX"
    assert len(sbom["components"]) == 2
    assert sbom["components"][0]["name"] == "lodash"
    assert sbom["components"][1]["name"] == "requests"
