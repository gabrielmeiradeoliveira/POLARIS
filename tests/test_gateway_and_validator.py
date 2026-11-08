"""Tests for AI Validation Gateway and AI Validator (GOALS 34 & 35)."""

from polaris.core.models import BudgetTracker, ExecutionBudget
from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding
from polaris.gateway.validation_gateway import AISkipReason, AIValidationGateway
from tests.test_hybrid_orchestrator import ScriptedProvider
from polaris.validator.ai_validator import AIValidationOutput, AIValidationVerdict, AIValidatorEngine


def test_ai_validation_gateway_skip_policy_and_caching():
    """Verify skip policy skips deterministically confirmed findings and hits cache."""
    gateway = AIValidationGateway()
    finding = CanonicalSecurityFinding(
        finding_id="find:12345",
        domain=CanonicalFindingDomain.CODE_INTELLIGENCE,
        title="Bypass in auth",
        severity="HIGH",
        confidence="CONFIRMED",
        file_path="auth.py",
        line=10,
        rule_or_cve="SEC-AUTH-002",
        evidence_text="return True",
        remediation_hint="Restore checks",
    )
    tracker = BudgetTracker(ExecutionBudget(max_total_tokens=5000, max_requests=5))

    # 1. Deterministic skip
    dec = gateway.evaluate(finding, "diff snippet", tracker, force_ai=False)
    assert dec.should_call_ai is False
    assert dec.skip_reason == AISkipReason.DETERMINISTIC_CONFIRMED

    # 2. Force AI -> Allowed with compressed prompt
    dec_force = gateway.evaluate(finding, "diff snippet", tracker, force_ai=True)
    assert dec_force.should_call_ai is True
    assert "Validate finding:" in dec_force.compressed_prompt

    # 3. Cache recording and hit
    gateway.record_cache(dec_force.cache_key, {"result": "ok"})
    dec_cached = gateway.evaluate(finding, "diff snippet", tracker, force_ai=True)
    assert dec_cached.should_call_ai is False
    assert dec_cached.skip_reason == AISkipReason.CACHE_HIT


def test_ai_validator_structured_output():
    """Verify AI Validator produces structured validated output."""
    provider = ScriptedProvider()
    finding = CanonicalSecurityFinding(
        finding_id="find:abc",
        domain=CanonicalFindingDomain.CONTAINER,
        title="Root user defect",
        severity="HIGH",
        confidence="CONFIRMED",
        file_path="Dockerfile",
        line=1,
        rule_or_cve="ROOT_USER_EXECUTION",
        evidence_text="missing USER",
        remediation_hint="Add USER appuser",
    )

    out = AIValidatorEngine.validate_finding(finding, "prompt", provider)
    assert isinstance(out, AIValidationOutput)
    assert out.verdict == AIValidationVerdict.CORROBORATED
    assert "USER appuser" in out.remediation_suggestion
