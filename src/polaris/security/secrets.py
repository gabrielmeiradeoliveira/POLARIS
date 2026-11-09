"""Secret Detection Scanner (GOAL 53 - Fase 8).

High-confidence deterministic scanner for hardcoded credentials, API keys, private keys,
and tokens. Features zero-leakage redaction in reports, logs, and fingerprints.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from polaris.security.contracts import ScannerMetadata, SecurityDomain, SecurityScannerV2
from polaris.security.models import CanonicalSecurityFindingV2, sanitize_secret_text


class SecretPattern(BaseModel):
    """Specification of high-confidence credential regex."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    title: str
    severity: str
    pattern: str
    remediation: str


HIGH_CONFIDENCE_PATTERNS: list[SecretPattern] = [
    SecretPattern(
        rule_id="SEC_PRIVATE_KEY",
        title="Exposed Private Key",
        severity="CRITICAL",
        pattern=r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        remediation="Revoke key immediately and migrate to an encrypted secrets vault.",
    ),
    SecretPattern(
        rule_id="SEC_AWS_ACCESS_KEY",
        title="Exposed AWS Access Key ID",
        severity="CRITICAL",
        pattern=r"(?:^|[^A-Z0-9])(AKIA[0-9A-Z]{16})(?:[^A-Z0-9]|$)",
        remediation="Revoke AWS key in IAM and replace with AWS IAM Roles or OIDC.",
    ),
    SecretPattern(
        rule_id="SEC_GITHUB_PAT",
        title="Exposed GitHub Personal Access Token",
        severity="CRITICAL",
        pattern=r"(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{30,})",
        remediation="Revoke GitHub token immediately in security settings.",
    ),
    SecretPattern(
        rule_id="SEC_SLACK_TOKEN",
        title="Exposed Slack Token",
        severity="HIGH",
        pattern=r"xox[baprs]-[0-9a-zA-Z]{10,}-[0-9a-zA-Z]{10,}",
        remediation="Revoke Slack bot/user token from Slack Developer Console.",
    ),
    SecretPattern(
        rule_id="SEC_PASSWORD_IN_URL",
        title="Password Embedded in URL",
        severity="HIGH",
        pattern=r"[a-zA-Z][a-zA-Z0-9+.-]*://[^:\s/]+:([^@\s/]{3,})@[^:\s/]+",
        remediation="Remove embedded basic-auth credentials from connection strings.",
    ),
    SecretPattern(
        rule_id="SEC_GENERIC_API_KEY",
        title="Hardcoded API Secret Assignment",
        severity="HIGH",
        pattern=r"""(?i)(?:api[_-]?key|secret[_-]?key|client[_-]?secret)\s*[:=]\s*['"][a-zA-Z0-9_\-\.]{16,}['"]""",
        remediation="Extract credentials to environment variables or local .env ignored by version control.",
    ),
]

# Patterns that clearly represent dummy / synthetic placeholders in tests or docs
PLACEHOLDER_REGEX = re.compile(
    r"(?:placeholder|my_token_here|your_token|dummy_key|my_secret|changeme|todo|<[a-z_]+>)",
    re.IGNORECASE,
)


class SecretDetectionScanner(SecurityScannerV2):
    """Deterministic, high-confidence secret scanner with zero credential leakage."""

    def __init__(self) -> None:
        self._compiled_patterns = [
            (p, re.compile(p.pattern, re.MULTILINE if "PRIVATE KEY" in p.pattern else 0))
            for p in HIGH_CONFIDENCE_PATTERNS
        ]

    @property
    def metadata(self) -> ScannerMetadata:
        return ScannerMetadata(
            scanner_id="secret_detection",
            name="Polaris Secret Detection Engine",
            version="2.0.0",
            domain=SecurityDomain.SECRETS,
            supported_file_patterns=["*"],
            description="Detects high-confidence exposed secrets, tokens, private keys, and passwords.",
            external_dependencies=[],
            is_optional=False,
        )

    def is_available(self) -> bool:
        return True

    def scan_file(self, file_path: str, content: str) -> list[CanonicalSecurityFindingV2]:
        """Scan file content and emit sanitized, redacted secret findings."""
        norm_path = file_path.replace("\\", "/").lower()

        # Skip binaries, lockfiles, or test fixtures explicitly containing harmless mocks
        if norm_path.endswith((".png", ".jpg", ".ico", ".woff", ".bin", ".pyc")):
            return []

        findings: list[CanonicalSecurityFindingV2] = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            trimmed = line.strip()
            if not trimmed:
                continue

            # Skip lines that are clearly documentation placeholders
            if PLACEHOLDER_REGEX.search(trimmed):
                continue

            for spec, regex in self._compiled_patterns:
                match = regex.search(trimmed)
                if match:
                    # Sanitize line before creating finding
                    redacted_snippet = sanitize_secret_text(trimmed)
                    findings.append(
                        CanonicalSecurityFindingV2.create(
                            scanner_id=self.metadata.scanner_id,
                            domain=SecurityDomain.SECRETS,
                            rule_or_cve=spec.rule_id,
                            title=spec.title,
                            file_path=file_path,
                            line=idx,
                            severity=spec.severity,
                            confidence="HIGH",
                            evidence_text=redacted_snippet,
                            remediation_hint=spec.remediation,
                            risk_score=95.0 if spec.severity == "CRITICAL" else 80.0,
                        )
                    )
                    break  # One finding per line is sufficient
        return findings
