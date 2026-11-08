"""Adversarial Offline Benchmark for POLARIS GOAL 29.9."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from polaris.core.models import (
    BudgetTracker,
    CandidateFinding,
    Confidence,
    ExecutionBudget,
    FindingCategory,
    Severity,
)
from polaris.intelligence.arbitration import ArbitrationStatus
from polaris.review.engine import HybridReviewOrchestrator
from tests.test_hybrid_orchestrator import ScriptedProvider


def run_adversarial_suite() -> dict[str, any]:
    """Execute adversarial scenarios covering security, contracts, and false positive controls."""
    orchestrator = HybridReviewOrchestrator()

    scenarios = [
        # Scenario 1: Critical Security Bypass (Unconditional True)
        {
            "id": "adv-sec-01",
            "file": "auth/check.py",
            "before": "def has_access(u): return u.is_admin\n",
            "after": "def has_access(u): return True\n",
            "diff": "@@ -1 +1 @@\n-def has_access(u): return u.is_admin\n+def has_access(u): return True\n",
            "expected_rule": "SEC-AUTH-002",
            "expected_status": ArbitrationStatus.CONFIRMED,
        },
        # Scenario 2: Tuple Return Contract Incompatibility
        {
            "id": "adv-con-02",
            "file": "api/user.py",
            "before": "def get_info(uid): return {'role': 'user'}\n",
            "after": "def get_info(uid): return ('user',)\n",
            "diff": "@@ -1 +1 @@\n-def get_info(uid): return {'role': 'user'}\n+def get_info(uid): return ('user',)\n",
            "related": {"web/client.py": "from api.user import get_info\ndef run(u): return get_info(u)['role']\n"},
            "expected_rule": "CONTRACT-001",
            "expected_status": ArbitrationStatus.SUSPECTED,
        },
        # Scenario 3: Clean Negative - Formatting only
        {
            "id": "adv-clean-03",
            "file": "calc/math.py",
            "before": "def calc(a, b): return (a + b)\n",
            "after": "def calc(a, b):\n    # Reformat\n    return (a + b)\n",
            "diff": "@@ -1 +1,2 @@\n-def calc(a, b): return (a + b)\n+def calc(a, b):\n+    return (a + b)\n",
            "expected_findings_count": 0,
        },
        # Scenario 4: Clean Negative - More Restrictive Security
        {
            "id": "adv-clean-04",
            "file": "auth/strict.py",
            "before": "def check(u): return u.is_active or u.is_admin\n",
            "after": "def check(u): return u.is_active and u.is_admin\n",
            "diff": "@@ -1 +1 @@\n-def check(u): return u.is_active or u.is_admin\n+def check(u): return u.is_active and u.is_admin\n",
            "expected_findings_count": 0,
        },
    ]

    results = []

    for sc in scenarios:
        provider = ScriptedProvider(off_findings=[])
        budget = ExecutionBudget(max_total_tokens=10_000, max_requests=10)
        tracker = BudgetTracker(budget)

        res = orchestrator.run_review(
            changed_file=sc["file"],
            before_content=sc.get("before"),
            after_content=sc["after"],
            diff_text=sc["diff"],
            provider=provider,
            tracker=tracker,
            related_files=sc.get("related", {}),
        )

        findings = res.arbitration.findings
        count = len(findings)

        passed = True
        if "expected_findings_count" in sc:
            passed = count == sc["expected_findings_count"]
        elif "expected_rule" in sc:
            passed = count >= 1 and findings[0].status == sc["expected_status"]

        results.append({
            "scenario_id": sc["id"],
            "passed": passed,
            "findings_count": count,
            "telemetry": res.telemetry.model_dump(),
        })

    all_passed = all(r["passed"] for r in results)
    return {"passed": all_passed, "total": len(results), "scenarios": results}


if __name__ == "__main__":
    report = run_adversarial_suite()
    out = Path("evaluations/reports/goal29_adversarial_benchmark.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Adversarial benchmark: {report['total']} scenarios. All passed: {report['passed']}")
