"""Tests for POLARIS Cross-File Contract Analysis (GOAL 28.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polaris.contracts.engine import CrossFileContractEngine
from polaris.contracts.models import ContractKind
from polaris.core.models import FindingCategory, Severity
from polaris.guardrails.models import GuardrailConfidence


def test_case_09_indirect_serializer_contract_reproduced():
    """Exact reproduction of Case 09 from end_to_end_context_benchmark.json across 3 files."""
    engine = CrossFileContractEngine()

    changed_file = "adapters/id.py"
    before_code = "def encode(x): return {'value': x}\n"
    after_code = "def encode(x): return x\n"

    related_files = {
        "mapping/user.py": "from adapters.id import encode\ndef map_user(x): return encode(x)\n",
        "messaging/publish.py": "from mapping.user import map_user\ndef publish(x): return map_user(x)['value']\n",
    }

    findings = engine.analyze_contracts(
        changed_file=changed_file,
        before_content=before_code,
        after_content=after_code,
        related_files=related_files,
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "CONTRACT-001"
    assert f.category == FindingCategory.TYPE_MISMATCH
    assert f.severity == Severity.HIGH
    assert f.file_path == "adapters/id.py"
    assert f.line_range.start_line == 1

    ev = f.evidence
    assert ev.origin_file == "adapters/id.py"
    assert ev.origin_symbol == "encode"
    assert ev.consumer_file == "messaging/publish.py"
    assert ev.consumer_symbol == "publish"
    assert ev.required_operation == "['value']"

    # Crucial check: parameter x has unproven type, so confidence must be SUSPECTED, not CONFIRMED
    assert ev.confidence == GuardrailConfidence.SUSPECTED
    assert len(ev.limitations) > 0
    assert "cannot be proven statically" in ev.limitations[0]

    # Verify propagation trail has 3 steps
    assert len(ev.propagation_path) == 3
    assert ev.propagation_path[0].symbol == "encode"
    assert ev.propagation_path[1].symbol == "map_user"
    assert ev.propagation_path[2].symbol == "publish"

    # Verify candidate finding conversion
    candidates = engine.to_candidate_findings(findings)
    assert len(candidates) == 1
    assert candidates[0].category == FindingCategory.TYPE_MISMATCH
    assert "CONTRACT-001" in candidates[0].title
    assert "adapters/id.py:1" in candidates[0].evidence


def test_proven_incompatibility_yields_confirmed():
    """When the changed return explicitly returns None or an incompatible literal, confidence is CONFIRMED."""
    engine = CrossFileContractEngine()

    changed_file = "adapters/id.py"
    before_code = "def encode(x): return {'value': x}\n"
    after_code = "def encode(x): return None\n"

    related_files = {
        "consumer.py": "from adapters.id import encode\ndef run(x): return encode(x)['value']\n",
    }

    findings = engine.analyze_contracts(
        changed_file=changed_file,
        before_content=before_code,
        after_content=after_code,
        related_files=related_files,
    )

    assert len(findings) == 1
    assert findings[0].evidence.confidence == GuardrailConfidence.CONFIRMED
    assert findings[0].evidence.after_contract.kind == ContractKind.NONE


def test_contract_preserved_no_finding():
    """If the new implementation still guarantees all required keys, no finding should be emitted."""
    engine = CrossFileContractEngine()

    changed_file = "adapters/id.py"
    before_code = "def encode(x): return {'value': x}\n"
    after_code = "def encode(x): return {'value': x, 'extra': 123}\n"

    related_files = {
        "consumer.py": "from adapters.id import encode\ndef run(x): return encode(x)['value']\n",
    }

    findings = engine.analyze_contracts(
        changed_file=changed_file,
        before_content=before_code,
        after_content=after_code,
        related_files=related_files,
    )

    assert len(findings) == 0


def test_consumer_updated_no_finding():
    """If consumer does not access the removed key, no finding should be emitted."""
    engine = CrossFileContractEngine()

    changed_file = "adapters/id.py"
    before_code = "def encode(x): return {'value': x, 'other': 1}\n"
    after_code = "def encode(x): return {'other': 1}\n"

    related_files = {
        # Consumer only needs 'other'
        "consumer.py": "from adapters.id import encode\ndef run(x): return encode(x)['other']\n",
    }

    findings = engine.analyze_contracts(
        changed_file=changed_file,
        before_content=before_code,
        after_content=after_code,
        related_files=related_files,
    )

    assert len(findings) == 0


def test_cyclic_calls_handled_safely():
    """Cyclic dependencies between functions must not cause infinite loops."""
    engine = CrossFileContractEngine(max_depth=5, max_nodes=20)

    changed_file = "a.py"
    before_code = "def f(x): return {'value': x}\n"
    after_code = "def f(x): return x\n"

    related_files = {
        "b.py": "from a import f\nfrom c import h\ndef g(x): return f(h(x))\n",
        "c.py": "from b import g\ndef h(x): return g(x)\n",
    }

    findings = engine.analyze_contracts(
        changed_file=changed_file,
        before_content=before_code,
        after_content=after_code,
        related_files=related_files,
    )

    # Terminates gracefully without RecursionError
    assert isinstance(findings, list)


def test_depth_and_node_limits_enforced():
    """Search terminates cleanly when max_depth is reached."""
    engine = CrossFileContractEngine(max_depth=2, max_nodes=5)

    changed_file = "a.py"
    before_code = "def f(x): return {'value': x}\n"
    after_code = "def f(x): return x\n"

    # Chain of depth 4: a -> b -> c -> d -> consumer
    related_files = {
        "b.py": "from a import f\ndef b_func(x): return f(x)\n",
        "c.py": "from b import b_func\ndef c_func(x): return b_func(x)\n",
        "d.py": "from c import c_func\ndef d_func(x): return c_func(x)['value']\n",
    }

    findings = engine.analyze_contracts(
        changed_file=changed_file,
        before_content=before_code,
        after_content=after_code,
        related_files=related_files,
    )

    # Because max_depth=2, it won't reach d.py
    assert len(findings) == 0


def test_syntax_error_handled_cleanly():
    """Files with syntax errors in related files must not crash the engine."""
    engine = CrossFileContractEngine()

    changed_file = "a.py"
    before_code = "def f(x): return {'value': x}\n"
    after_code = "def f(x): return x\n"

    related_files = {
        "b.py": "def invalid syntax ::: error\n",
    }

    findings = engine.analyze_contracts(
        changed_file=changed_file,
        before_content=before_code,
        after_content=after_code,
        related_files=related_files,
    )

    assert len(findings) == 0


def test_oversized_file_ignored():
    """Files larger than max_file_size_bytes must be ignored."""
    engine = CrossFileContractEngine(max_file_size_bytes=50)

    changed_file = "a.py"
    before_code = "def f(x): return {'value': x}\n"
    after_code = "def f(x): return x\n"

    related_files = {
        "b.py": "# " + ("x" * 100) + "\nfrom a import f\ndef g(x): return f(x)['value']\n",
    }

    findings = engine.analyze_contracts(
        changed_file=changed_file,
        before_content=before_code,
        after_content=after_code,
        related_files=related_files,
    )

    assert len(findings) == 0


def test_determinism_and_idempotence():
    """Identical runs must produce strictly identical findings and propagation paths."""
    engine = CrossFileContractEngine()

    changed_file = "adapters/id.py"
    before_code = "def encode(x): return {'value': x}\n"
    after_code = "def encode(x): return x\n"

    related_files = {
        "mapping/user.py": "from adapters.id import encode\ndef map_user(x): return encode(x)\n",
        "messaging/publish.py": "from mapping.user import map_user\ndef publish(x): return map_user(x)['value']\n",
    }

    run1 = engine.analyze_contracts(changed_file, before_code, after_code, related_files)
    run2 = engine.analyze_contracts(changed_file, before_code, after_code, related_files)

    assert len(run1) == len(run2) == 1
    assert run1[0].model_dump() == run2[0].model_dump()
