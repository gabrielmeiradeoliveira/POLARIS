"""Unified Security Evidence Platform (GOAL 33).

Correlates findings across Code Intelligence (AST/Dataflow/Guardrails),
Supply Chain (CVEs/SBOM), and Container Security into canonical evidence bundles.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from polaris.container.scanner import DockerfileFinding
from polaris.supply_chain.scanner import MatchedVulnerability, VulnerabilityMatchStatus


class CanonicalFindingDomain(StrEnum):
    """Domain originating the security evidence."""

    CODE_INTELLIGENCE = "CODE_INTELLIGENCE"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    CONTAINER = "CONTAINER"
    SECRETS = "SECRETS"
    IAC = "IAC"
    IMAGE_VULNERABILITY = "IMAGE_VULNERABILITY"


class CanonicalSecurityFinding(BaseModel):
    """Normalized, canonical representation of a security risk across all engines."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    domain: CanonicalFindingDomain
    title: str
    severity: str
    confidence: str
    file_path: str
    line: int
    rule_or_cve: str
    evidence_text: str
    remediation_hint: str
    risk_score: float = 50.0

    @classmethod
    def from_supply_chain(cls, match: MatchedVulnerability) -> CanonicalSecurityFinding:
        """Map supply chain match to canonical finding."""
        cve = match.advisory.cve_id or match.advisory.advisory_id
        seed = f"SUPPLY_CHAIN::{match.dependency.manifest_file}::{match.dependency.name}::{cve}"
        fid = f"find:{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
        return cls(
            finding_id=fid,
            domain=CanonicalFindingDomain.SUPPLY_CHAIN,
            title=f"Vulnerable dependency '{match.dependency.name}' affected by {cve}",
            severity=match.advisory.severity,
            confidence="CONFIRMED" if match.status == VulnerabilityMatchStatus.CONFIRMED_AFFECTED else "POSSIBLE",
            file_path=match.dependency.manifest_file,
            line=1,
            rule_or_cve=cve,
            evidence_text=match.evidence,
            remediation_hint=f"Upgrade '{match.dependency.name}' to fixed version '{match.advisory.fixed_version or 'latest'}'."
            if match.advisory.fixed_version
            else "Review dependency advisory for mitigation.",
            risk_score=85.0 if match.advisory.severity == "CRITICAL" else 70.0,
        )

    @classmethod
    def from_container(cls, finding: DockerfileFinding, file_path: str = "Dockerfile") -> CanonicalSecurityFinding:
        """Map Dockerfile finding to canonical finding."""
        seed = f"CONTAINER::{file_path}::{finding.line}::{finding.defect_type.value}"
        fid = f"find:{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
        return cls(
            finding_id=fid,
            domain=CanonicalFindingDomain.CONTAINER,
            title=f"Container configuration defect: {finding.defect_type.value}",
            severity=finding.severity,
            confidence="CONFIRMED",
            file_path=file_path,
            line=finding.line,
            rule_or_cve=finding.defect_type.value,
            evidence_text=finding.instruction,
            remediation_hint=finding.remediation,
            risk_score=90.0 if finding.severity == "CRITICAL" else 65.0,
        )


class UnifiedEvidencePlatform:
    """Consolidates security intelligence across code, dependencies, and containers."""

    @classmethod
    def correlate_findings(
        cls,
        code_findings: list[Any],
        supply_chain_matches: list[MatchedVulnerability],
        container_findings: list[DockerfileFinding],
    ) -> list[CanonicalSecurityFinding]:
        """Produce unified, deduplicated list of canonical security findings."""
        unified: list[CanonicalSecurityFinding] = []

        # 1. Supply Chain
        for m in supply_chain_matches:
            if m.status in (VulnerabilityMatchStatus.CONFIRMED_AFFECTED, VulnerabilityMatchStatus.POSSIBLY_AFFECTED):
                unified.append(CanonicalSecurityFinding.from_supply_chain(m))

        # 2. Containers
        for cf in container_findings:
            unified.append(CanonicalSecurityFinding.from_container(cf))

        # Sort deterministically by risk_score desc, then file_path
        return sorted(unified, key=lambda x: (-x.risk_score, x.file_path, x.line))
