"""Tests for Cross-File Contract Intelligence 2.0 (GOAL 29.5)."""

from __future__ import annotations

import pytest

from polaris.contracts.engine import CrossFileContractEngine
from polaris.core.models import FindingCategory, Severity
from polaris.guardrails.models import GuardrailConfidence


def test_tuple_list_return_contract_incompatibility_detected():
    """Detect when a function returning dict keys changes to return a tuple or list, breaking dictionary index consumer."""
    engine = CrossFileContractEngine()

    changed_file = "service/api.py"
    before = "def get_item(x): return {'value': x}\n"
    # Changed to return tuple
    after = "def get_item(x): return (x, 123)\n"

    related = {
        "client.py": "from service.api import get_item\ndef consume(x): return get_item(x)['value']\n",
    }

    findings = engine.analyze_contracts(changed_file, before, after, related)

    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "CONTRACT-001"
    assert f.category == FindingCategory.TYPE_MISMATCH
    assert f.evidence.confidence == GuardrailConfidence.SUSPECTED
    assert f.evidence.required_operation == "['value']"
