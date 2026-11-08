"""Tests for GitHub PR Review, Quality Gates, and SARIF Formatting (GOALS 36, 37, 38)."""

import hashlib
import hmac
from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding
from polaris.integrations.github.review_native import GitHubNativeReviewEngine, ReviewCommentSide
from polaris.policy.quality_gate import GateDecision, PolarisSecurityPolicy, SecurityQualityGateEngine
from polaris.reporting.sarif import SarifReportFormatter


def test_github_webhook_hmac_sha256_verification():
    """Verify webhook signature validation protects against unauthenticated payloads."""
    payload = b'{"action":"opened"}'
    secret = "polaris_webhook_secret_key"
    valid_sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert GitHubNativeReviewEngine.verify_webhook_signature(payload, secret, valid_sig) is True
    assert GitHubNativeReviewEngine.verify_webhook_signature(payload, secret, "sha256=invalid") is False
    assert GitHubNativeReviewEngine.verify_webhook_signature(payload, secret, "") is False


def test_quality_gate_decision_and_suppression():
    """Verify policy evaluation and finding suppression workflow."""
    finding_crit = CanonicalSecurityFinding(
        finding_id="find:crit1",
        domain=CanonicalFindingDomain.CODE_INTELLIGENCE,
        title="Critical bypass",
        severity="CRITICAL",
        confidence="CONFIRMED",
        file_path="auth.py",
        line=5,
        rule_or_cve="SEC-AUTH-002",
        evidence_text="return True",
        remediation_hint="Restore checks",
    )

    # 1. Without suppression -> FAIL
    dec, blocking = SecurityQualityGateEngine.evaluate([finding_crit])
    assert dec == GateDecision.FAIL
    assert len(blocking) == 1

    # 2. With suppression -> PASS
    policy = PolarisSecurityPolicy(suppressed_finding_ids=["find:crit1"])
    dec_supp, blocking_supp = SecurityQualityGateEngine.evaluate([finding_crit], policy=policy)
    assert dec_supp == GateDecision.PASS
    assert len(blocking_supp) == 0


def test_sarif_v210_export_format():
    """Verify standard SARIF output generation."""
    finding = CanonicalSecurityFinding(
        finding_id="find:123",
        domain=CanonicalFindingDomain.CONTAINER,
        title="Unpinned image tag",
        severity="HIGH",
        confidence="CONFIRMED",
        file_path="Dockerfile",
        line=1,
        rule_or_cve="UNPINNED_LATEST_TAG",
        evidence_text="FROM python:latest",
        remediation_hint="Pin tag",
    )

    sarif = SarifReportFormatter.to_sarif([finding])
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"][0]["results"]) == 1
    assert sarif["runs"][0]["results"][0]["ruleId"] == "UNPINNED_LATEST_TAG"
