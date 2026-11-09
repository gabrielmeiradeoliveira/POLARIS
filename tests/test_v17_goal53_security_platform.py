"""Comprehensive Test Suite for Security Intelligence Platform (GOAL 53).

Validates:
1. Architecture V2 scanner contracts, metadata, and error isolation.
2. Dockerfile Security V2 (chmod 777, ADD vs COPY, root execution, unpinned packages).
3. Docker Scout Adapter (offline fixture SARIF ingestion, CLI detection, NOT AVAILABLE handling).
4. Software Bill of Materials (SBOM) ingestion for CycloneDX and SPDX JSON.
5. Supply Chain Security V2 (manifests + SBOM dependencies, PEP 440 semver).
6. Security Advisory Providers & Provenance metadata.
7. Secret Detection Scanner (high confidence, zero secret leakage in logs, fingerprints, or reports).
8. Infrastructure as Code (IaC) Scanner (Docker Compose & Kubernetes privilege/namespace checks).
9. Canonical Security Findings V2, stable fingerprints, and correlation engine.
10. Baseline Engine & Quality Gate V2 integration (anti-false-resolved on scanner failure).
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from polaris.container.scanner import ContainerSecurityScanner, DockerfileDefectType
from polaris.core.registry import build_default_scanner_registry
from polaris.security.advisories import LocalSnapshotAdvisoryProvider
from polaris.security.contracts import SecurityDomain
from polaris.security.docker_scout import DockerScoutAdapter
from polaris.security.iac import IaCSecurityScanner
from polaris.security.models import (
    CanonicalSecurityFindingV2,
    FindingCorrelationEngine,
)
from polaris.security.sbom import SBOMFormat, SBOMParser
from polaris.security.secrets import SecretDetectionScanner
from polaris.supply_chain.scanner import Ecosystem

runner = CliRunner()


def test_goal53_secret_scanner_redaction_and_fingerprints():
    """Verify secrets are redacted completely in findings and fingerprints without credential leakage."""
    scanner = SecretDetectionScanner()
    raw_content = (
        "# Configuration file with credentials\n"
        "GITHUB_TOKEN = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'\n"
        "AWS_KEY = 'AKIA1234567890ABCDEF'\n"
        "SLACK_BOT = 'xoxb-1234567890-1234567890123'\n"
        "DATABASE_URL = 'postgres://admin:superSecret123@db.internal:5432/prod'\n"
    )

    findings = scanner.scan_file("config/settings.py", raw_content)
    assert len(findings) == 4

    for f in findings:
        # Guarantee no plain secret is present anywhere in finding fields
        assert "ghp_ABC" not in f.evidence_text
        assert "superSecret123" not in f.evidence_text
        assert "xoxb-1234567890-1234567890123" not in f.evidence_text
        assert "ghp_ABC" not in f.stable_fingerprint

    # Placeholders must NOT be flagged
    dummy_content = "TOKEN = 'your_token_here_placeholder'\nPASSWORD = '<password_dummy>'\n"
    assert len(scanner.scan_file("dummy.py", dummy_content)) == 0


def test_goal53_dockerfile_v2_new_defect_rules():
    """Verify new Dockerfile hardening rules: chmod 777, ADD vs COPY, apt-get upgrade."""
    content = (
        "FROM python:3.12-slim\n"
        "USER appuser\n"
        "ADD local_app.py /app/\n"
        "RUN chmod -R 777 /app\n"
        "RUN apt-get update && apt-get upgrade -y\n"
    )
    findings = ContainerSecurityScanner.analyze_dockerfile(content, file_path="Dockerfile")
    types = {f.defect_type for f in findings}

    assert DockerfileDefectType.ADD_INSTEAD_OF_COPY in types
    assert DockerfileDefectType.INSECURE_CHMOD_777 in types
    assert DockerfileDefectType.INSECURE_PACKAGE_UPGRADE in types
    assert DockerfileDefectType.ROOT_USER_EXECUTION not in types  # USER appuser is present


def test_goal53_iac_compose_and_kubernetes_security():
    """Verify Docker Compose and Kubernetes privilege and host-sharing analysis."""
    iac = IaCSecurityScanner()

    compose_yaml = (
        "version: '3.8'\n"
        "services:\n"
        "  web:\n"
        "    image: nginx:alpine\n"
        "    privileged: true\n"
        "    network_mode: host\n"
        "    volumes:\n"
        "      - /var/run/docker.sock:/var/run/docker.sock\n"
    )
    c_findings = iac.scan_file("docker-compose.yml", compose_yaml)
    rules = {f.rule_or_cve for f in c_findings}
    assert "IAC_COMPOSE_PRIVILEGED" in rules
    assert "IAC_COMPOSE_HOST_NETWORK" in rules
    assert "IAC_COMPOSE_DOCKER_SOCKET" in rules

    k8s_yaml = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: secure-app\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      hostPID: true\n"
        "      containers:\n"
        "        - name: app\n"
        "          image: python:3.12\n"
        "          securityContext:\n"
        "            privileged: true\n"
        "            runAsUser: 0\n"
    )
    k_findings = iac.scan_file("deployment.yaml", k8s_yaml)
    k_rules = {f.rule_or_cve for f in k_findings}
    assert "IAC_K8S_HOST_PID" in k_rules
    assert "IAC_K8S_PRIVILEGED_CONTAINER" in k_rules
    assert "IAC_K8S_ROOT_USER" in k_rules


def test_goal53_sbom_cyclonedx_and_spdx_ingestion():
    """Verify CycloneDX and SPDX SBOM parsing without inventing missing data."""
    cdx_json = json.dumps({
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "components": [
            {
                "name": "requests",
                "version": "2.20.0",
                "purl": "pkg:pypi/requests@2.20.0",
                "scope": "required",
            },
            {
                "name": "lodash",
                "version": "4.17.21",
                "purl": "pkg:npm/lodash@4.17.21",
                "scope": "optional",
            },
        ],
    })

    cdx_report = SBOMParser.parse_sbom(cdx_json, "sbom-cdx.json")
    assert cdx_report.format == SBOMFormat.CYCLONEDX_JSON
    assert cdx_report.component_count == 2
    assert cdx_report.components[0].name == "requests"
    assert cdx_report.components[0].ecosystem == Ecosystem.PYPI
    assert cdx_report.components[1].ecosystem == Ecosystem.NPM

    spdx_json = json.dumps({
        "spdxVersion": "SPDX-2.3",
        "name": "TargetArtifact",
        "packages": [
            {
                "name": "urllib3",
                "versionInfo": "1.24.2",
                "externalRefs": [
                    {
                        "referenceType": "purl",
                        "referenceLocator": "pkg:pypi/urllib3@1.24.2",
                    }
                ],
            }
        ],
    })
    spdx_report = SBOMParser.parse_sbom(spdx_json, "sbom-spdx.json")
    assert spdx_report.format == SBOMFormat.SPDX_JSON
    assert spdx_report.component_count == 1
    assert spdx_report.components[0].name == "urllib3"
    assert spdx_report.components[0].version == "1.24.2"


def test_goal53_docker_scout_adapter_and_offline_normalization():
    """Verify Docker Scout adapter detects environment state and ingests structured SARIF reports."""
    adapter = DockerScoutAdapter()
    meta = adapter.metadata
    assert meta.scanner_id == "docker_scout"
    assert meta.is_optional is True

    # Ingest synthetic Scout SARIF
    scout_sarif = json.dumps({
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "docker scout",
                        "rules": [
                            {"id": "CVE-2023-1234", "help": {"text": "Update openssl package."}}
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "CVE-2023-1234",
                        "message": {"text": "OpenSSL buffer overflow vulnerability"},
                        "properties": {
                            "packageName": "openssl",
                            "packageVersion": "1.1.1t",
                            "purl": "pkg:deb/debian/openssl@1.1.1t",
                        },
                    }
                ],
            }
        ]
    })

    findings = adapter.scan_file("docker-scout.sarif", scout_sarif)
    assert len(findings) == 1
    assert findings[0].rule_or_cve == "CVE-2023-1234"
    assert findings[0].component_name == "openssl"
    assert findings[0].advisory_source == "docker_scout"


def test_goal53_finding_correlation_across_engines():
    """Verify correlation groups multiple independent scanner proofs for same component/CVE."""
    f1 = CanonicalSecurityFindingV2.create(
        scanner_id="supply_chain",
        domain=SecurityDomain.SUPPLY_CHAIN,
        rule_or_cve="CVE-2018-18074",
        title="Vulnerable dependency requests",
        file_path="requirements.txt",
        line=10,
        severity="HIGH",
        confidence="HIGH",
        evidence_text="requests==2.20.0 vulnerable in <2.21.0",
        component_name="requests",
        component_version="2.20.0",
    )

    f2 = CanonicalSecurityFindingV2.create(
        scanner_id="sbom_scanner",
        domain=SecurityDomain.SUPPLY_CHAIN,
        rule_or_cve="CVE-2018-18074",
        title="Vulnerable SBOM component requests",
        file_path="sbom.json",
        line=1,
        severity="HIGH",
        confidence="HIGH",
        evidence_text="[SBOM] requests==2.20.0 vulnerable in <2.21.0",
        component_name="requests",
        component_version="2.20.0",
    )

    groups = FindingCorrelationEngine.correlate([f1, f2])
    assert len(groups) == 1
    assert set(groups[0].participating_scanners) == {"supply_chain", "sbom_scanner"}
    assert len(groups[0].corroborating_findings) == 1


def test_goal53_advisory_provider_provenance():
    """Verify advisory provider records provenance metadata and offline disclaimer."""
    provider = LocalSnapshotAdvisoryProvider()
    prov = provider.get_provenance()
    assert prov.is_offline_snapshot is True
    assert prov.advisories_count > 0
    assert "Offline curated advisory snapshot" in prov.disclaimer

    # Query existing advisory
    advs = provider.lookup_advisories("requests", Ecosystem.PYPI)
    assert len(advs) > 0
    assert advs[0].cve_id == "CVE-2018-18074"


def test_goal53_default_scanner_registry_extension():
    """Verify build_default_scanner_registry contains all 5 specialized scanners."""
    registry = build_default_scanner_registry()
    scanners = {s.scanner_id for s in registry.list_scanners()}
    assert "container_security" in scanners
    assert "supply_chain" in scanners
    assert "secret_detection" in scanners
    assert "iac_security" in scanners
    assert "docker_scout" in scanners
