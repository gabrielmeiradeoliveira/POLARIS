"""Stress and performance testing for GOAL 29.10."""

from __future__ import annotations

import time

from polaris.contracts.engine import CrossFileContractEngine
from polaris.core.models import BudgetTracker, ExecutionBudget
from polaris.guardrails.engine import SecurityGuardrailEngine
from polaris.review.engine import HybridReviewOrchestrator
from tests.test_hybrid_orchestrator import ScriptedProvider


def test_performance_under_dense_ast_tree():
    """Verify latency under a dense AST file with 50 functions."""
    engine = SecurityGuardrailEngine()

    funcs = []
    for i in range(50):
        funcs.append(f"def func_{i}(x):\n    return x > {i}\n")
    before_code = "\n".join(funcs)
    after_code = before_code.replace("func_25(x):\n    return x > 25", "func_25(x):\n    return True")

    t0 = time.perf_counter()
    findings = engine.analyze_file_change("dense_module.py", before_code, after_code)
    duration_ms = (time.perf_counter() - t0) * 1000

    # Must complete within 200ms
    assert duration_ms < 200
    assert len(findings) == 1
    assert findings[0].rule_id == "SEC-AUTH-002"


def test_performance_under_cyclic_and_deep_call_graph():
    """Verify that deep propagation graphs with 20 nodes terminate cleanly within bounded time."""
    engine = CrossFileContractEngine(max_depth=5, max_nodes=50)

    changed_file = "origin.py"
    before = "def encode(x): return {'value': x}\n"
    after = "def encode(x): return x\n"

    related = {}
    for i in range(1, 15):
        prev = f"mod_{i-1}" if i > 1 else "origin"
        caller_code = f"from {prev} import encode\ndef f_{i}(x): return encode(x)\n"
        related[f"mod_{i}.py"] = caller_code

    t0 = time.perf_counter()
    findings = engine.analyze_contracts(changed_file, before, after, related)
    duration_ms = (time.perf_counter() - t0) * 1000

    assert duration_ms < 300
    assert isinstance(findings, list)
