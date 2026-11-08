"""Security Quality Gates and Policy Engine (GOAL 37).

Evaluates findings against declarative polaris.yaml policy thresholds,
managing baseline comparisons and suppressions.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from polaris.evidence.platform import CanonicalSecurityFinding


class GateDecision(StrEnum):
    """Quality gate decision."""

    PASS = "PASS"  # noqa: S105
    WARN = "WARN"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class PolarisSecurityPolicy(BaseModel):
    """Declarative security policy configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fail_on_severity: list[str] = Field(default_factory=lambda: ["CRITICAL", "HIGH"])
    allow_suppressions: bool = True
    suppressed_finding_ids: list[str] = Field(default_factory=list)
    max_tolerated_vulnerabilities: int = 0


class SecurityQualityGateEngine:
    """Evaluates canonical security findings against policy thresholds."""

    @classmethod
    def evaluate(
        cls,
        findings: list[CanonicalSecurityFinding],
        policy: PolarisSecurityPolicy | None = None,
    ) -> tuple[GateDecision, list[str]]:
        """Evaluate findings against policy."""
        pol = policy or PolarisSecurityPolicy()
        blocking_findings: list[str] = []

        for f in findings:
            if pol.allow_suppressions and f.finding_id in pol.suppressed_finding_ids:
                continue

            if f.severity.upper() in [s.upper() for s in pol.fail_on_severity]:
                blocking_findings.append(f"[{f.severity}] {f.title} ({f.rule_or_cve}) at {f.file_path}:{f.line}")

        if len(blocking_findings) > pol.max_tolerated_vulnerabilities:
            return GateDecision.FAIL, blocking_findings
        elif blocking_findings:
            return GateDecision.WARN, blocking_findings
        return GateDecision.PASS, []
