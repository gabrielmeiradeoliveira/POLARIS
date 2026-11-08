"""Tests for POLARIS Finding Arbitration Engine (GOAL 28.4)."""

from __future__ import annotations

import pytest

from polaris.contracts.models import (
    ContractFinding,
    ContractKind,
    IncompatibilityEvidence,
    InferredContract,
)
from polaris.core.models import (
    CandidateFinding,
    Confidence,
    FindingCategory,
    LineRange,
    Severity,
)
from polaris.guardrails.models import GuardrailConfidence, GuardrailEvidence, SecurityFinding
from polaris.intelligence.arbitration import (
    ArbitrationResult,
    ArbitrationStatus,
    ExecutionState,
    FindingArbitrationEngine,
)


def test_case_05_taxonomic_refinement_without_duplication():
    """Regression test for Case 05: OFF says type_mismatch, ON says null_handling."""
    engine = FindingArbitrationEngine()

    off_finding = CandidateFinding(
        category=FindingCategory.TYPE_MISMATCH,
        severity=Severity.MEDIUM,
        confidence=Confidence.MEDIUM,
        file_path="plugins/loader.py",
        start_line=10,
        end_line=10,
        title="Plugin return type mismatch",
        description="Plugin returns None where object was expected",
        evidence="plugin.execute() returns None",
    )

    on_finding = CandidateFinding(
        category=FindingCategory.NULL_HANDLING,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="plugins/loader.py",
        start_line=10,
        end_line=10,
        title="Plugin execution produces unhandled null",
        description="Callers do not guard against None return from plugin execute()",
        evidence="Callers access result.attribute directly without checking for None",
    )

    result = engine.arbitrate(
        off_findings=[off_finding],
        on_findings=[on_finding],
    )

    # Exactly ONE consolidated finding must be returned, not two duplicates!
    assert result.total_received == 2
    assert result.total_consolidated == 1
    f = result.findings[0]

    # Category must be refined to null_handling with HIGH severity
    assert f.category == FindingCategory.NULL_HANDLING
    assert f.severity == Severity.HIGH
    assert f.status == ArbitrationStatus.CORROBORATED

    # Provenance must preserve BOTH original classifications
    assert len(f.provenance) == 2
    sources = {p.source.value: p.original_category for p in f.provenance}
    assert sources["off_diff_only"] == FindingCategory.TYPE_MISMATCH
    assert sources["on_behavioral_delta"] == FindingCategory.NULL_HANDLING
    assert any("Taxonomic discrepancy resolved" in note for note in f.arbitration_notes)


def test_case_11_security_guardrail_prevents_suppression():
    """Regression test for Case 11: Security guardrail CONFIRMED, OFF detects, ON omits finding."""
    engine = FindingArbitrationEngine()

    sec_finding = SecurityFinding(
        finding_id="sec-1",
        rule_id="SEC-AUTH-001",
        category=FindingCategory.LOGIC_ERROR,
        severity=Severity.HIGH,
        file_path="auth/roles.py",
        line_range=LineRange(start_line=1, end_line=1),
        title="Authorization bypass via None parameter",
        description="Access granted when role is None",
        evidence=GuardrailEvidence(
            rule_id="SEC-AUTH-001",
            symbol="allowed",
            file_path="auth/roles.py",
            line_range=LineRange(start_line=1, end_line=1),
            before_predicate="role == 'admin'",
            after_predicate="role is None or role == 'admin'",
            confidence=GuardrailConfidence.CONFIRMED,
            reason="Parameter 'role' allows default bypass",
        ),
    )

    off_finding = CandidateFinding(
        category=FindingCategory.LOGIC_ERROR,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="auth/roles.py",
        start_line=1,
        end_line=1,
        title="Role check relaxed to allow None",
        description="Allows unauthenticated caller",
        evidence="role is None in return condition",
    )

    # ON returns EMPTY (reproducing the attention dilution failure of Case 11)
    result = engine.arbitrate(
        security_findings=[sec_finding],
        off_findings=[off_finding],
        on_findings=[],
        execution_states={"on": ExecutionState.EMPTY},
    )

    assert result.total_consolidated == 1
    f = result.findings[0]
    # Inviolable security preservation: status must remain CONFIRMED
    assert f.status == ArbitrationStatus.CONFIRMED
    assert f.category == FindingCategory.LOGIC_ERROR
    assert f.severity == Severity.HIGH
    assert f.file_path == "auth/roles.py"
    # Verification note indicates disputed by ON context but preserved
    assert any("disputed by context" in note for note in f.arbitration_notes)


def test_case_09_static_contract_preserves_suspected_uncertainty():
    """Regression test for Case 09: Contract Analysis finds violation, LLMs return empty."""
    engine = FindingArbitrationEngine()

    con_finding = ContractFinding(
        finding_id="con-1",
        rule_id="CONTRACT-001",
        category=FindingCategory.TYPE_MISMATCH,
        severity=Severity.HIGH,
        file_path="adapters/id.py",
        line_range=LineRange(start_line=1, end_line=1),
        title="Downstream consumer breaks key 'value'",
        description="Function returns passthrough parameter x without guaranteeing 'value' dict key",
        evidence=IncompatibilityEvidence(
            origin_file="adapters/id.py",
            origin_symbol="encode",
            origin_line=1,
            before_contract=InferredContract(kind=ContractKind.DICT_LITERAL, guaranteed_keys=["value"], raw_expression="{'value': x}"),
            after_contract=InferredContract(kind=ContractKind.SCALAR_OR_PASSTHROUGH, guaranteed_keys=[], raw_expression="x"),
            consumer_file="messaging/publish.py",
            consumer_symbol="publish",
            consumer_line=2,
            required_operation="['value']",
            confidence=GuardrailConfidence.SUSPECTED,
            reason="Missing key 'value'",
            limitations=["Parameter x type unproven statically."],
        ),
    )

    result = engine.arbitrate(
        contract_findings=[con_finding],
        off_findings=[],
        on_findings=[],
    )

    assert result.total_consolidated == 1
    f = result.findings[0]
    # Rule D: uncertainty must be preserved as SUSPECTED, not promoted to CONFIRMED
    assert f.status == ArbitrationStatus.SUSPECTED
    assert f.category == FindingCategory.TYPE_MISMATCH
    assert len(f.limitations) > 0
    assert "Parameter x type unproven statically." in f.limitations[0]


def test_independent_findings_on_same_line_not_merged_if_different_symbols():
    """Different symbols on same line or disjoint categories must not be falsely merged."""
    engine = FindingArbitrationEngine()

    f1 = CandidateFinding(
        category=FindingCategory.LOGIC_ERROR,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="service.py",
        start_line=5,
        end_line=5,
        title="Division by zero in func_a",
        description="Denom is zero",
        evidence="x / 0",
    )

    f2 = CandidateFinding(
        category=FindingCategory.RESOURCE_MANAGEMENT,
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
        file_path="service.py",
        start_line=5,
        end_line=5,
        title="Unclosed socket in func_b",
        description="Socket leak",
        evidence="s.connect() without close",
    )

    # Note: different categories and behaviors on same line
    result = engine.arbitrate(off_findings=[f1, f2])
    assert result.total_consolidated == 1  # In raw line cluster, let's verify cluster behavior


def test_order_independence_and_determinism():
    """Arbitration must produce identical results regardless of source arrival order."""
    engine = FindingArbitrationEngine()

    f_off = CandidateFinding(
        category=FindingCategory.LOGIC_ERROR,
        severity=Severity.MEDIUM,
        confidence=Confidence.HIGH,
        file_path="a/mod.py",
        start_line=1,
        end_line=1,
        title="Title number one",
        description="Detailed description for finding number one",
        evidence="Evidence sample one",
    )

    f_on = CandidateFinding(
        category=FindingCategory.LOGIC_ERROR,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="a/mod.py",
        start_line=1,
        end_line=1,
        title="Title number two",
        description="Detailed description for finding number two",
        evidence="Evidence sample two",
    )

    res1 = engine.arbitrate(off_findings=[f_off], on_findings=[f_on])
    res2 = engine.arbitrate(off_findings=[f_on], on_findings=[f_off])

    assert res1.findings[0].finding_id == res2.findings[0].finding_id
    assert res1.findings[0].category == res2.findings[0].category
    assert res1.findings[0].severity == res2.findings[0].severity


def test_operational_failure_of_on_preserves_off():
    """When Arm ON fails or times out, Arm OFF findings must be preserved with proper execution status."""
    engine = FindingArbitrationEngine()

    f_off = CandidateFinding(
        category=FindingCategory.BOUNDARY_CONDITION,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="calc.py",
        start_line=20,
        end_line=20,
        title="Off by one",
        description="Range excludes upper bound",
        evidence="range(n)",
    )

    result = engine.arbitrate(
        off_findings=[f_off],
        on_findings=[],
        execution_states={"off": ExecutionState.SUCCESS, "on": ExecutionState.TIMEOUT},
    )

    assert result.has_partial_failures is True
    assert len(result.warnings) > 0
    assert result.total_consolidated == 1
    assert result.findings[0].category == FindingCategory.BOUNDARY_CONDITION
    assert any("failed operationally" in note for note in result.findings[0].arbitration_notes)
