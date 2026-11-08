"""Tests for Advanced Contract Intelligence (GOAL 30 - Fase 30.7)."""

import ast
from polaris.contracts.advanced_contract_engine import AdvancedContractAnalyzer, ContractViolationType


def test_missing_required_argument_contract_violation():
    """Verify detection when producer removes default or adds required parameter and caller omits it."""
    producer_code = "def send_email(to_addr: str, subject: str, body: str): pass"
    consumer_code = "def notify_user(): send_email('user@test.local', 'Welcome')"

    prod_ast = ast.parse(producer_code).body[0]
    cons_ast = ast.parse(consumer_code).body[0]

    sig = AdvancedContractAnalyzer.inspect_function_signature(prod_ast)
    call_node = cons_ast.body[0].value

    violations = AdvancedContractAnalyzer.check_call_against_signature(
        call_node=call_node,
        signature=sig,
        consumer_symbol="notify_user",
        consumer_file="services/notifier.py",
    )

    assert len(violations) == 1
    assert violations[0].violation_type == ContractViolationType.MISSING_REQUIRED_ARGUMENT
    assert "body" in violations[0].message


def test_unexpected_keyword_argument_violation():
    """Verify detection when caller passes unknown keyword argument without **kwargs."""
    producer_code = "def query(sql: str, timeout: int = 30): pass"
    consumer_code = "def fetch(): query('SELECT 1', retries=3)"

    prod_ast = ast.parse(producer_code).body[0]
    cons_ast = ast.parse(consumer_code).body[0]

    sig = AdvancedContractAnalyzer.inspect_function_signature(prod_ast)
    call_node = cons_ast.body[0].value

    violations = AdvancedContractAnalyzer.check_call_against_signature(
        call_node=call_node,
        signature=sig,
        consumer_symbol="fetch",
        consumer_file="services/db.py",
    )

    assert len(violations) == 1
    assert violations[0].violation_type == ContractViolationType.UNEXPECTED_KEYWORD_ARGUMENT
    assert "retries" in violations[0].message
