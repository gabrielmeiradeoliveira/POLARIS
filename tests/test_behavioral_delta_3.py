"""Tests for Behavioral Delta 3.0 (GOAL 30 - Fase 30.8)."""

import ast
from polaris.context.behavioral_delta_3 import BehavioralDelta3, SemanticChangeCategory


def test_behavioral_delta_detects_removed_validation_call():
    """Verify detection when a security/validation call is deleted in a function."""
    before_code = """
def process_payment(user_id: str, amount: float):
    validate_account_status(user_id)
    return gateway.charge(amount)
"""
    after_code = """
def process_payment(user_id: str, amount: float):
    return gateway.charge(amount)
"""
    before_fn = ast.parse(before_code).body[0]
    after_fn = ast.parse(after_code).body[0]

    changes = BehavioralDelta3.compare_functions(before_fn, after_fn, file_path="billing.py")

    assert len(changes) >= 1
    assert any(c.category == SemanticChangeCategory.CRITICAL_CALL_REMOVED for c in changes)
    assert any("validate_account_status" in c.before_repr for c in changes)
