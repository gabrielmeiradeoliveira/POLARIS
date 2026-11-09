"""Canonical Security Findings V2, Normalization, Correlation & Deduplication Engine (GOAL 53).

Unifies findings across Container, Docker Scout, Supply Chain, SBOM, Secrets, IaC,
and Code Intelligence into verified canonical representations with stable, collision-free
fingerprints, correlation groups, and secret redaction guarantees.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from polaris.security.contracts import SecurityDomain


def sanitize_secret_text(text: str) -> str:
    """Ensure raw secret materials or tokens are permanently redacted from findings and logs."""
    if not text:
        return ""
    # Redact typical token shapes
    patterns = [
        (r"(ghp_[a-zA-Z0-9]{20,})", "ghp_[REDACTED]"),
        (r"(gho_[a-zA-Z0-9]{20,})", "gho_[REDACTED]"),
        (r"(github_pat_[a-zA-Z0-9_]{30,})", "github_pat_[REDACTED]"),
        (r"(xox[baprs]-[0-9a-zA-Z]{10,}-[0-9a-zA-Z]{10,})", "xox-[REDACTED]"),
        (r"(AKIA[0-9A-Z]{16})", "AKIA[REDACTED]"),
        (r"(-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----)", "[REDACTED PRIVATE KEY]"),
        (r"(bearer\s+)([a-zA-Z0-9_\-\.]{15,})", r"\1[REDACTED]"),
        (r"((?:password|secret|api[_-]?key|token)\s*[:=]\s*['\"])[^'\"]{6,}(['\"])", r"\1[REDACTED]\2"),
        (r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:\s/]+:)([^@\s/]{3,})(@[^:\s/]+)", r"\1[REDACTED]\3"),
    ]
    redacted = text
    for pattern, repl in patterns:
        redacted = re.sub(pattern, repl, redacted, flags=re.IGNORECASE)
    return redacted


def compute_canonical_v2_fingerprint(
    domain: SecurityDomain,
    file_path: str,
    rule_or_cve: str,
    evidence_text: str,
    component: str | None = None,
    version: str | None = None,
) -> str:
    """Compute line-drift-tolerant canonical fingerprint for Security V2 findings."""
    norm_domain = domain.value.upper()
    norm_path = file_path.replace("\\", "/").strip().lower().lstrip("./")
    norm_rule = rule_or_cve.strip().upper()
    norm_comp = (component or "").strip().lower()
    norm_ver = (version or "").strip().lower()
    norm_ev = re.sub(r"\s+", " ", sanitize_secret_text(evidence_text)).strip().lower()

    seed = f"{norm_domain}|{norm_path}|{norm_comp}|{norm_ver}|{norm_rule}|{norm_ev}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return f"bl-{digest}"


class CanonicalSecurityFindingV2(BaseModel):
    """Normalized, canonical representation of a security risk across all scanners in V2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str = Field(..., min_length=1)
    stable_fingerprint: str = Field(..., min_length=1)
    scanner_id: str = Field(..., min_length=1)
    domain: SecurityDomain
    rule_or_cve: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    severity: str = "MEDIUM"
    confidence: str = "HIGH"
    file_path: str = Field(..., min_length=1)
    line: int = 1
    evidence_text: str = ""
    remediation_hint: str = ""
    component_name: str | None = None
    component_version: str | None = None
    purl: str | None = None
    cve_id: str | None = None
    ghsa_id: str | None = None
    advisory_source: str = "local"
    data_timestamp: str | None = None
    correlation_key: str | None = None
    risk_score: float = 50.0

    @classmethod
    def create(
        cls,
        scanner_id: str,
        domain: SecurityDomain,
        rule_or_cve: str,
        title: str,
        file_path: str,
        line: int,
        severity: str,
        confidence: str,
        evidence_text: str,
        remediation_hint: str = "",
        component_name: str | None = None,
        component_version: str | None = None,
        purl: str | None = None,
        cve_id: str | None = None,
        ghsa_id: str | None = None,
        advisory_source: str = "local",
        risk_score: float = 50.0,
    ) -> CanonicalSecurityFindingV2:
        clean_evidence = sanitize_secret_text(evidence_text)
        clean_remediation = sanitize_secret_text(remediation_hint)
        fp = compute_canonical_v2_fingerprint(
            domain=domain,
            file_path=file_path,
            rule_or_cve=rule_or_cve,
            evidence_text=clean_evidence,
            component=component_name,
            version=component_version,
        )
        fid = f"find:{hashlib.sha256(f'{scanner_id}::{fp}'.encode()).hexdigest()[:16]}"

        # Build logical correlation key: package/component + version + cve
        corr_key = None
        if component_name and rule_or_cve:
            corr_key = f"{domain.value}::{component_name.lower()}::{component_version or 'any'}::{rule_or_cve.upper()}"
        elif domain == SecurityDomain.SECRETS:
            corr_key = f"SECRETS::{clean_evidence}"

        return cls(
            finding_id=fid,
            stable_fingerprint=fp,
            scanner_id=scanner_id,
            domain=domain,
            rule_or_cve=rule_or_cve,
            title=title,
            severity=severity.upper(),
            confidence=confidence.upper(),
            file_path=file_path.replace("\\", "/"),
            line=max(1, line),
            evidence_text=clean_evidence,
            remediation_hint=clean_remediation,
            component_name=component_name,
            component_version=component_version,
            purl=purl,
            cve_id=cve_id,
            ghsa_id=ghsa_id,
            advisory_source=advisory_source,
            data_timestamp=datetime.now(UTC).isoformat(),
            correlation_key=corr_key,
            risk_score=risk_score,
        )


class CorrelatedFindingGroup(BaseModel):
    """A collection of findings originating from different scanners referencing the same underlying risk."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    primary_finding: CanonicalSecurityFindingV2
    corroborating_findings: list[CanonicalSecurityFindingV2] = Field(default_factory=list)
    participating_scanners: list[str] = Field(default_factory=list)


class FindingCorrelationEngine:
    """Groups and correlates findings across independent scanners without losing distinct evidence."""

    @classmethod
    def correlate(cls, findings: list[CanonicalSecurityFindingV2]) -> list[CorrelatedFindingGroup]:
        """Group findings by correlation_key or stable_fingerprint preserving individual proofs."""
        groups_by_key: dict[str, list[CanonicalSecurityFindingV2]] = {}
        ungrouped: list[CanonicalSecurityFindingV2] = []

        for f in findings:
            key = f.correlation_key or f.stable_fingerprint
            if key:
                groups_by_key.setdefault(key, []).append(f)
            else:
                ungrouped.append(f)

        correlated_groups: list[CorrelatedFindingGroup] = []

        # Process grouped findings deterministically
        for key in sorted(groups_by_key):
            items = groups_by_key[key]
            # Primary finding is the one with highest severity or highest risk score
            sorted_items = sorted(
                items,
                key=lambda x: (
                    {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(x.severity, 0),
                    x.risk_score,
                    x.scanner_id,
                ),
                reverse=True,
            )
            primary = sorted_items[0]
            corroborating = sorted_items[1:]
            scanners = sorted(list({x.scanner_id for x in sorted_items}))
            correlated_groups.append(
                CorrelatedFindingGroup(
                    primary_finding=primary,
                    corroborating_findings=corroborating,
                    participating_scanners=scanners,
                )
            )

        for u in ungrouped:
            correlated_groups.append(
                CorrelatedFindingGroup(
                    primary_finding=u,
                    corroborating_findings=[],
                    participating_scanners=[u.scanner_id],
                )
            )

        return correlated_groups
