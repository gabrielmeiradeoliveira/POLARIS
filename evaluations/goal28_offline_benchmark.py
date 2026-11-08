"""Offline benchmark evaluating Hybrid Review Engine against simulated OFF and ON baselines (GOAL 28.6)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add repo root to sys.path
sys.path.insert(0, ".")

from polaris.core.models import (
    BudgetTracker,
    CandidateFinding,
    Confidence,
    ExecutionBudget,
    FindingCategory,
    Severity,
)
from polaris.providers.fake import FakeProvider
from polaris.review.engine import HybridReviewOrchestrator
from tests.test_hybrid_orchestrator import ScriptedProvider


def run_offline_hybrid_benchmark() -> dict[str, any]:
    """Execute offline benchmark comparing simulated DIRECT (OFF vs ON) against HYBRID strategy."""
    fixtures_file = Path("evaluations/fixtures/end_to_end_context_benchmark.json")
    if not fixtures_file.exists():
        return {"error": "Fixtures file missing"}

    cases = json.loads(fixtures_file.read_text(encoding="utf-8"))
    orchestrator = HybridReviewOrchestrator()

    results = []

    for case in cases:
        cid = case.get("case_id", "")
        diff_text = case.get("diff_text", "")
        file_contents = case.get("file_contents", {})

        # Identify primary changed file
        changed_file = next(iter(file_contents.keys())) if file_contents else "main.py"
        after_content = file_contents.get(changed_file, "")
        related = {k: v for k, v in file_contents.items() if k != changed_file}

        # Setup scripted provider simulating benchmark findings
        off_findings = []
        on_findings = []

        if "05" in cid:
            # Case 5
            off_findings = [
                CandidateFinding(
                    category=FindingCategory.TYPE_MISMATCH,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    file_path=changed_file,
                    start_line=1,
                    end_line=1,
                    title="Plugin return type mismatch",
                    description="Plugin returns None where object was expected",
                    evidence="plugin returns None",
                )
            ]
            on_findings = [
                CandidateFinding(
                    category=FindingCategory.NULL_HANDLING,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    file_path=changed_file,
                    start_line=1,
                    end_line=1,
                    title="Unhandled null in plugin execution",
                    description="Callers do not guard against None return from plugin execute()",
                    evidence="Caller crashes on None",
                )
            ]
        elif "11" in cid:
            # Case 11
            off_findings = [
                CandidateFinding(
                    category=FindingCategory.LOGIC_ERROR,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    file_path=changed_file,
                    start_line=1,
                    end_line=1,
                    title="Authorization check relaxed to accept None",
                    description="Allows unauthenticated caller access",
                    evidence="role is None in return condition",
                )
            ]
            on_findings = []  # Attention dilution suppression in Arm ON
        elif "09" in cid:
            # Case 9
            off_findings = []
            on_findings = []

        provider = ScriptedProvider(off_findings=off_findings, on_findings=on_findings)
        budget = ExecutionBudget(max_total_tokens=10_000, max_requests=10)
        tracker = BudgetTracker(budget)

        # Before code reconstruction heuristic for test
        before_content = None
        if "05" in cid:
            before_content = "def execute(): return {'status': 'ok'}\n"
        elif "11" in cid:
            before_content = "def allowed(role=None):\n    return role == 'admin'\n"
        elif "09" in cid:
            before_content = "def encode(x): return {'value': x}\n"

        res = orchestrator.run_review(
            changed_file=changed_file,
            before_content=before_content,
            after_content=after_content,
            diff_text=diff_text,
            provider=provider,
            tracker=tracker,
            related_files=related,
        )

        results.append({
            "case_id": cid,
            "findings_count": len(res.arbitration.findings),
            "findings": [f.model_dump() for f in res.arbitration.findings],
            "telemetry": res.telemetry.model_dump(),
        })

    return {"status": "success", "total_cases": len(results), "cases": results}


if __name__ == "__main__":
    report = run_offline_hybrid_benchmark()
    out_path = Path("evaluations/reports/goal28_offline_benchmark.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Offline benchmark executed for {report['total_cases']} cases. Report saved to {out_path}")
