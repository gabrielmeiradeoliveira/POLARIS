from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AttackPath:
    id: str
    severity: str
    title: str
    evidence: list[str]
    confidence: str = "HIGH"


def detect_toxic_combinations(issues: list[dict[str, Any]]) -> list[AttackPath]:
    """Correlate findings across Code + SCA + IaC + Secrets into CRITICAL_ATTACK_PATH alerts."""
    paths: list[AttackPath] = []
    rule_ids = {str(i.get("ruleId", "")) for i in issues}
    has_public_api = any("NO_AUTH" in r or "PUBLIC_ENDPOINT" in r for r in rule_ids)
    has_high_vuln = any(
        i.get("severity") in ("CRITICAL", "BLOCKER") and i.get("confidence", "HIGH") == "HIGH"
        for i in issues
    )
    has_root_container = any("K8S-SEC-001" in r or "privileged" in r.lower() for r in rule_ids)
    has_kev = any("KEV" in r for r in rule_ids)
    has_secret = any("SECRET_EXPOSED" in r for r in rule_ids)

    if has_public_api and has_high_vuln:
        paths.append(
            AttackPath(
                id="aspm:EXPOSED_CRITICAL_ENDPOINT",
                severity="BLOCKER",
                title="EXPOSED_CRITICAL_ENDPOINT: Public API without auth combined with HIGH confidence vulnerability",
                evidence=["Public/unauthenticated endpoint", "HIGH-confidence vulnerability"],
            )
        )
    if has_root_container and has_kev and has_secret:
        paths.append(
            AttackPath(
                id="aspm:CONTAINER_ESCAPE_AND_COMPROMISE",
                severity="BLOCKER",
                title="CONTAINER_ESCAPE_AND_COMPROMISE: Privileged container + KEV CVE + Exposed Secret",
                evidence=["Privileged container (IaC)", "CISA KEV CVE", "Exposed secret"],
            )
        )
    return paths


def verify_hmac_signature(payload_bytes: bytes, signature_hex: str, secret: str) -> bool:
    """Verify X-Polaris-Signature HMAC-SHA256 in constant time."""
    if not signature_hex or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex.strip().lower())
