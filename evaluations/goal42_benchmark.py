"""Reproducible Performance & Critical Path Benchmark for POLARIS v1.5 (GOAL 42).

Measures core critical paths deterministically in-memory:
1. ContextRanker top-k priority selection, token-budget packing, and deterministic tie-breaking.
2. Interprocedural contract inference and AST visitor analysis.
3. HybridReviewOrchestrator unified pipeline dispatch (direct mode, guardrails + contracts).

Includes warm-up, multiple iterations, median, mean, standard deviation, and RSD calculations.
"""

from __future__ import annotations

import ast
import json
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Any

from polaris.context.behavioral_delta import BehavioralChange, SemanticChangeCategory
from polaris.context.context_ranker import ContextRanker, RankedContextSnippet
from polaris.context.impact_analysis import ImpactClassification, ImpactedConsumer
from polaris.contracts.consumer_tracker import infer_return_contract
from polaris.core.models import BudgetTracker, ExecutionBudget
from polaris.providers.fake import FakeProvider
from polaris.review.engine import HybridReviewOrchestrator


@dataclass
class BenchmarkMetric:
    name: str
    warmup_runs: int
    measured_runs: int
    raw_times_ms: list[float]
    mean_ms: float
    median_ms: float
    stdev_ms: float
    rsd_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "warmup_runs": self.warmup_runs,
            "measured_runs": self.measured_runs,
            "mean_ms": round(self.mean_ms, 3),
            "median_ms": round(self.median_ms, 3),
            "stdev_ms": round(self.stdev_ms, 3),
            "rsd_pct": round(self.rsd_pct, 2),
        }


def run_benchmark_series(
    name: str,
    func: Any,
    warmup_runs: int = 2,
    measured_runs: int = 7,
) -> BenchmarkMetric:
    # Warmup
    for _ in range(warmup_runs):
        func()

    # Measured runs
    times: list[float] = []
    for _ in range(measured_runs):
        start = time.perf_counter()
        func()
        elapsed = (time.perf_counter() - start) * 1000.0
        times.append(elapsed)

    mean_val = statistics.mean(times)
    median_val = statistics.median(times)
    stdev_val = statistics.stdev(times) if len(times) > 1 else 0.0
    rsd_val = (stdev_val / mean_val * 100.0) if mean_val > 0 else 0.0

    return BenchmarkMetric(
        name=name,
        warmup_runs=warmup_runs,
        measured_runs=measured_runs,
        raw_times_ms=times,
        mean_ms=mean_val,
        median_ms=median_val,
        stdev_ms=stdev_val,
        rsd_pct=rsd_val,
    )


def benchmark_context_ranker(items_count: int = 500) -> Any:
    changed_files = [f"src/module_{i % 10}/file_{i}.py" for i in range(10)]
    impacted = [
        ImpactedConsumer(
            consumer_id=f"consumer_{i}",
            consumer_name=f"caller_{i}",
            file_path=f"src/consumer_{i % 50}.py",
            classification=ImpactClassification.DIRECT if i % 2 == 0 else ImpactClassification.TRANSITIVE,
            dependency_path=[f"src/consumer_{i % 50}.py", f"src/module_{i % 10}/file_{i}.py"],
            reason=f"Call to modified function {i}",
        )
        for i in range(items_count)
    ]
    behavioral = [
        BehavioralChange(
            category=SemanticChangeCategory.CRITICAL_CALL_REMOVED if i % 3 == 0 else SemanticChangeCategory.RETURN_VALUE_MODIFIED,
            description=f"Behavioral change in function {i}",
            file_path=f"src/module_{i % 10}/file_{i}.py",
            line=10,
            before_repr="authenticate_token()",
            after_repr="None",
            symbol_name=f"func_{i}",
        )
        for i in range(items_count)
    ]
    file_contents = {
        f"src/consumer_{i}.py": f"def caller_{i}():\n    return {i}\n" for i in range(50)
    }
    for f in changed_files:
        file_contents[f] = "def changed(): pass\n"

    def workload() -> list[RankedContextSnippet]:
        return ContextRanker.rank_context(
            changed_files=changed_files,
            impacted_consumers=impacted,
            behavioral_changes=behavioral,
            file_contents=file_contents,
            max_tokens=3000,
        )

    return workload


def benchmark_contract_ast_inference() -> Any:
    code_samples = [
        """
def compute_metrics(data: dict) -> dict:
    return {"total": len(data), "valid": True, "score": 98.5}
""",
        """
def validate_user(user_id: int) -> dict:
    if user_id <= 0:
        return {}
    return {"id": user_id, "active": True}
""",
        """
def lookup_config(key: str) -> str:
    return key.upper()
""",
    ]
    parsed_trees = [ast.parse(code) for code in code_samples]

    def workload() -> list[Any]:
        results = []
        for tree in parsed_trees:
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    contract = infer_return_contract(node)
                    results.append(contract)
        return results

    return workload


def benchmark_orchestrator_pipeline() -> Any:
    orchestrator = HybridReviewOrchestrator()
    provider = FakeProvider(scripted_responses=["Review pass complete."])
    budget = ExecutionBudget(max_requests=10, max_total_tokens=10000)
    tracker = BudgetTracker(budget=budget)

    changed_file = "src/calculator.py"
    before_content = "def add(a: int, b: int) -> int:\n    return a + b\n"
    after_content = "def add(a: int, b: int) -> int:\n    if a == 0:\n        return b\n    return a + b\n"
    diff_text = """--- a/src/calculator.py
+++ b/src/calculator.py
@@ -1,2 +1,4 @@
 def add(a: int, b: int) -> int:
+    if a == 0:
+        return b
     return a + b
"""

    def workload() -> Any:
        # Direct mode (static checks + deterministic contract evaluation)
        return orchestrator.run_review(
            changed_file=changed_file,
            before_content=before_content,
            after_content=after_content,
            diff_text=diff_text,
            provider=provider,
            tracker=tracker,
            related_files={},
        )

    return workload


def main() -> int:
    print("====================================================================")
    print("POLARIS v1.5 — GOAL 42 Critical Path Performance Benchmark")
    print("====================================================================")
    print(f"Python Runtime: {sys.version.split()[0]} on {sys.platform}")
    print("Baseline Status: Single-Environment Deterministic Baseline Measurement")
    print("Historical Baseline Note: No separate frozen v1.4 benchmark artifact exists.")
    print("Benchmarking canonical consolidated implementation against critical path SLA.\n")

    benchmarks = [
        ("ContextRanker.rank_candidates (500 items)", benchmark_context_ranker(500)),
        ("Contract.infer_return_contract (AST)", benchmark_contract_ast_inference()),
        ("HybridReviewOrchestrator (Deterministic Direct)", benchmark_orchestrator_pipeline()),
    ]

    results = []
    for name, workload_fn in benchmarks:
        print(f"Benchmarking: {name}...")
        metric = run_benchmark_series(name=name, func=workload_fn, warmup_runs=2, measured_runs=7)
        results.append(metric.to_dict())
        print(f"  -> Median: {metric.median_ms:.3f} ms | Mean: {metric.mean_ms:.3f} ms | Stdev: {metric.stdev_ms:.3f} ms | RSD: {metric.rsd_pct:.2f}%\n")

    output_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "python_version": sys.version,
            "platform": sys.platform,
        },
        "methodology": {
            "warmup_runs": 2,
            "measured_runs": 7,
            "data_source": "Deterministic in-memory synthetic & AST nodes",
            "comparison_status": "Current Canonical Implementation Characterization",
        },
        "results": results,
    }

    print("====================================================================")
    print("Benchmark Completed Successfully.")
    print(json.dumps(output_payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
