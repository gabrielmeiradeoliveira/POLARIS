"""Tests for POLARIS Security Guardrail Engine (GOAL 28.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polaris.core.models import FindingCategory, Severity
from polaris.guardrails.engine import SecurityGuardrailEngine
from polaris.guardrails.models import GuardrailConfidence


def test_case_11_authorization_relaxation_detected():
    """Test exact reproduction of Case 11 from end_to_end_context_benchmark.json."""
    engine = SecurityGuardrailEngine()

    before_code = "def allowed(role=None):\n    return role == 'admin'\n"
    after_code = "def allowed(role=None):\n    return role is None or role == 'admin'\n"

    findings = engine.analyze_file_change(
        file_path="auth/roles.py",
        before_content=before_code,
        after_content=after_code,
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "SEC-AUTH-001"
    assert f.category == FindingCategory.LOGIC_ERROR
    assert f.severity == Severity.HIGH
    assert f.file_path == "auth/roles.py"
    assert f.evidence.confidence == GuardrailConfidence.CONFIRMED
    assert f.evidence.symbol == "allowed"
    assert "role" in f.evidence.reason
    assert f.evidence.before_predicate == "role == 'admin'"
    assert "role is None or role == 'admin'" in f.evidence.after_predicate

    # Verify CandidateFinding conversion
    candidates = engine.to_candidate_findings(findings)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.category == FindingCategory.LOGIC_ERROR
    assert c.severity == Severity.HIGH
    assert "SEC-AUTH-001" in c.title


def test_identical_or_formatting_change_no_finding():
    """Formatting or identical code should not trigger any security alert."""
    engine = SecurityGuardrailEngine()

    before_code = "def allowed(role=None):\n    return role == 'admin'\n"
    after_code = "def allowed(role=None):\n    # Formatting only\n    return (role == 'admin')\n"

    findings = engine.analyze_file_change(
        file_path="auth/roles.py",
        before_content=before_code,
        after_content=after_code,
    )

    assert len(findings) == 0


def test_more_restrictive_change_no_finding():
    """Changes that make access more restrictive must NOT trigger an alert."""
    engine = SecurityGuardrailEngine()

    before_code = "def allowed(role=None):\n    return role is None or role == 'admin'\n"
    after_code = "def allowed(role=None):\n    return role == 'admin'\n"

    findings = engine.analyze_file_change(
        file_path="auth/roles.py",
        before_content=before_code,
        after_content=after_code,
    )

    assert len(findings) == 0


def test_no_finding_merely_due_to_security_names():
    """Presence of keywords like 'auth', 'security', 'role' without relaxation must not trigger alerts."""
    engine = SecurityGuardrailEngine()

    before_code = "def check_security_role(auth_context):\n    return auth_context.is_valid()\n"
    after_code = "def check_security_role(auth_context):\n    return auth_context.is_valid() and auth_context.is_admin()\n"

    findings = engine.analyze_file_change(
        file_path="security/auth_service.py",
        before_content=before_code,
        after_content=after_code,
    )

    assert len(findings) == 0


def test_unresolved_dynamic_call_marked_suspected():
    """When the predicate includes unresolved external function calls, confidence is SUSPECTED."""
    engine = SecurityGuardrailEngine()

    before_code = "def check_access(role=None):\n    return role == 'admin'\n"
    # Introduces role is None alongside a dynamic function call
    after_code = "def check_access(role=None):\n    return role is None or external_verifier(role)\n"

    findings = engine.analyze_file_change(
        file_path="auth/checker.py",
        before_content=before_code,
        after_content=after_code,
    )

    assert len(findings) == 1
    assert findings[0].evidence.confidence == GuardrailConfidence.SUSPECTED


def test_syntax_error_handled_gracefully():
    """Files with syntax errors should be handled without uncaught exceptions."""
    engine = SecurityGuardrailEngine()

    before_code = "def allowed(role=None):\n    return role == 'admin'\n"
    after_code = "def allowed(role=None):\n    return role is None or ::: broken syntax\n"

    findings = engine.analyze_file_change(
        file_path="auth/broken.py",
        before_content=before_code,
        after_content=after_code,
    )

    assert len(findings) == 0


def test_determinism_and_idempotence():
    """Identical runs must produce strictly identical results."""
    engine = SecurityGuardrailEngine()

    before_code = "def allowed(role=None):\n    return role == 'admin'\n"
    after_code = "def allowed(role=None):\n    return role is None or role == 'admin'\n"

    run1 = engine.analyze_file_change("auth/roles.py", before_code, after_code)
    run2 = engine.analyze_file_change("auth/roles.py", before_code, after_code)

    assert len(run1) == len(run2) == 1
    assert run1[0].model_dump() == run2[0].model_dump()


def test_max_file_size_limit_respected():
    """Oversized files should be skipped cleanly."""
    engine = SecurityGuardrailEngine(max_file_size_bytes=100)

    before_code = "def allowed(role=None):\n    return role == 'admin'\n"
    after_code = "# Large padding " + ("x" * 200) + "\ndef allowed(role=None):\n    return role is None or role == 'admin'\n"

    findings = engine.analyze_file_change("auth/roles.py", before_code, after_code)
    assert len(findings) == 0
