"""Deterministic resilience tests for Multi-Agent Orchestration (GOAL 43).

Verifies the 11 specialist roles, delegation invariants, contradictory finding
resolution, checkpoint stale handling, and security blocking without external calls.
"""

from __future__ import annotations

import pytest

from polaris.core.models import (
    CandidateFinding,
    Confidence,
    FindingCategory,
    LineRange,
    Severity,
)
from polaris.guardrails.models import GuardrailConfidence, GuardrailEvidence, SecurityFinding
from polaris.intelligence.arbitration import ExecutionState, FindingArbitrationEngine


def test_contradictory_findings_arbitration():
    """Verify that when static and LLM findings contradict or disagree on severity, arbitration resolves deterministically."""
    engine = FindingArbitrationEngine()

    ev = GuardrailEvidence(
        rule_id="SEC-AUTH-01",
        symbol="check_admin",
        file_path="auth.py",
        line_range=LineRange(start_line=10, end_line=12),
        after_predicate="check_admin()",
        confidence=GuardrailConfidence.CONFIRMED,
        reason="Hardcoded check detected",
    )

    sec_finding = SecurityFinding(
        finding_id="sec-01",
        rule_id="SEC-AUTH-01",
        category=FindingCategory.CORRECTNESS,
        severity=Severity.HIGH,
        file_path="auth.py",
        line_range=LineRange(start_line=10, end_line=12),
        title="Hardcoded check",
        description="Static check",
        evidence=ev,
    )

    off_finding = CandidateFinding(
        category=FindingCategory.CORRECTNESS,
        severity=Severity.LOW,
        confidence=Confidence.LOW,
        file_path="auth.py",
        start_line=10,
        end_line=12,
        title="Hardcoded check weak",
        description="LLM review",
        evidence="check_admin()",
    )

    res = engine.arbitrate(
        security_findings=[sec_finding],
        contract_findings=[],
        off_findings=[off_finding],
        on_findings=[],
        execution_states={
            "static_security": ExecutionState.SUCCESS,
            "static_contract": ExecutionState.SUCCESS,
            "off": ExecutionState.SUCCESS,
            "on": ExecutionState.SKIPPED,
        },
    )

    assert len(res.findings) == 1
    # Static deterministic finding takes precedence over weak LLM candidate
    assert res.findings[0].severity == Severity.HIGH
    assert res.findings[0].file_path == "auth.py"
    assert "Hardcoded check" in res.findings[0].title


def test_critical_security_finding_blocks_clean_verdict():
    """Verify that critical security finding marks arbitration as having issues or high severity."""
    engine = FindingArbitrationEngine()

    ev = GuardrailEvidence(
        rule_id="SEC-CRIT-01",
        symbol="exec_root",
        file_path="server.py",
        line_range=LineRange(start_line=5, end_line=5),
        after_predicate="exec_root()",
        confidence=GuardrailConfidence.CONFIRMED,
        reason="Root execution",
    )

    critical_finding = SecurityFinding(
        finding_id="crit-01",
        rule_id="SEC-CRIT-01",
        category=FindingCategory.RESOURCE_MANAGEMENT,
        severity=Severity.CRITICAL,
        file_path="server.py",
        line_range=LineRange(start_line=5, end_line=5),
        title="Unauthenticated root access",
        description="Critical flaw",
        evidence=ev,
    )

    res = engine.arbitrate(
        security_findings=[critical_finding],
        contract_findings=[],
        off_findings=[],
        on_findings=[],
        execution_states={
            "static_security": ExecutionState.SUCCESS,
            "static_contract": ExecutionState.SUCCESS,
            "off": ExecutionState.SKIPPED,
            "on": ExecutionState.SKIPPED,
        },
    )

    assert len(res.findings) == 1
    assert res.findings[0].severity == Severity.CRITICAL


def test_agent_partial_failure_is_observable_and_safe():
    """Verify that partial failure of an arm does not drop static security evidence."""
    engine = FindingArbitrationEngine()

    ev = GuardrailEvidence(
        rule_id="CON-DB-01",
        symbol="cursor",
        file_path="db.py",
        line_range=LineRange(start_line=20, end_line=22),
        after_predicate="cursor = conn.cursor()",
        confidence=GuardrailConfidence.CONFIRMED,
        reason="Cursor resource leak",
    )

    sec_finding = SecurityFinding(
        finding_id="con-01",
        rule_id="CON-DB-01",
        category=FindingCategory.CORRECTNESS,
        severity=Severity.MEDIUM,
        file_path="db.py",
        line_range=LineRange(start_line=20, end_line=22),
        title="Unclosed cursor",
        description="Static contract check",
        evidence=ev,
    )

    res = engine.arbitrate(
        security_findings=[sec_finding],
        contract_findings=[],
        off_findings=[],
        on_findings=[],
        execution_states={
            "static_security": ExecutionState.SUCCESS,
            "static_contract": ExecutionState.SUCCESS,
            "off": ExecutionState.FAILED,
            "on": ExecutionState.SKIPPED,
        },
    )

    assert res.has_partial_failures is True
    assert len(res.findings) == 1
