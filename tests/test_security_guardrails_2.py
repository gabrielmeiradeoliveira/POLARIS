"""Tests for Security Guardrails 2.0 (GOAL 29.4)."""

from __future__ import annotations

import pytest

from polaris.core.models import FindingCategory, Severity
from polaris.guardrails.engine import SecurityGuardrailEngine
from polaris.guardrails.models import GuardrailConfidence


def test_sec_auth_002_unconditional_true_bypass_detected():
    """Detect when a conditional authorization check is replaced by unconditional return True."""
    engine = SecurityGuardrailEngine()

    before = "def is_authorized(user):\n    return user.is_authenticated and user.has_perm('write')\n"
    after = "def is_authorized(user):\n    return True\n"

    findings = engine.analyze_file_change("security/access.py", before, after)

    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "SEC-AUTH-002"
    assert f.severity == Severity.CRITICAL
    assert f.category == FindingCategory.LOGIC_ERROR
    assert f.evidence.confidence == GuardrailConfidence.CONFIRMED
    assert "replaced with unconditional True" in f.evidence.reason


def test_sec_auth_002_more_restrictive_false_no_bypass():
    """Replacing check with unconditional False makes it more restrictive (deny-all), not a bypass."""
    engine = SecurityGuardrailEngine()

    before = "def is_authorized(user):\n    return user.is_authenticated\n"
    after = "def is_authorized(user):\n    return False\n"

    findings = engine.analyze_file_change("security/access.py", before, after)
    assert len(findings) == 0
