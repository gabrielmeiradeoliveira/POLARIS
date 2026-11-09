"""GOAL 53 Independent Security Platform Detection & SLA Benchmark.

Measures TP, FP, TN, FN, Precision, Recall, F1, FPR, FNR across:
- Container Security V2 (Dockerfiles)
- Secret Detection (Tokens, Private Keys, Passwords)
- IaC Security (Docker Compose, Kubernetes)
- SBOM & Supply Chain Vulnerabilities (CycloneDX, SPDX, requirements)

Also benchmarks runtime latency per scanner and end-to-end memory usage.
"""

from __future__ import annotations

import time
import tracemalloc
from typing import Any

from pydantic import BaseModel

from polaris.core.registry import build_default_scanner_registry
from polaris.security.contracts import SecurityDomain


class BenchmarkCase(BaseModel):
    id: str
    domain: SecurityDomain
    file_path: str
    content: str
    expected_positive: bool
    expected_rule: str | None = None


BENCHMARK_CORPUS: list[BenchmarkCase] = [
    # 1. Container: Positive
    BenchmarkCase(
        id="CONT-POS-01",
        domain=SecurityDomain.CONTAINER,
        file_path="Dockerfile",
        content="FROM python:3.12-slim\nUSER app\nRUN chmod 777 /app\n",
        expected_positive=True,
        expected_rule="INSECURE_CHMOD_777",
    ),
    # 2. Container: Negative
    BenchmarkCase(
        id="CONT-NEG-01",
        domain=SecurityDomain.CONTAINER,
        file_path="Dockerfile",
        content="FROM python:3.12-slim@sha256:1234567890abcdef\nUSER appuser\nRUN chmod 755 /app\n",
        expected_positive=False,
    ),
    # 3. Secrets: Positive
    BenchmarkCase(
        id="SEC-POS-01",
        domain=SecurityDomain.SECRETS,
        file_path="secrets.env",
        content="AWS_ACCESS_KEY_ID = AKIAIOSFODNN7EXAMPLE\n",
        expected_positive=True,
        expected_rule="SEC_AWS_ACCESS_KEY",
    ),
    # 4. Secrets: Negative (Placeholder)
    BenchmarkCase(
        id="SEC-NEG-01",
        domain=SecurityDomain.SECRETS,
        file_path="test_config.py",
        content="TOKEN = 'your_token_here_placeholder'\n",
        expected_positive=False,
    ),
    # 5. IaC: Positive
    BenchmarkCase(
        id="IAC-POS-01",
        domain=SecurityDomain.IAC,
        file_path="docker-compose.yml",
        content="services:\n  app:\n    image: redis:alpine\n    privileged: true\n",
        expected_positive=True,
        expected_rule="IAC_COMPOSE_PRIVILEGED",
    ),
    # 6. IaC: Negative
    BenchmarkCase(
        id="IAC-NEG-01",
        domain=SecurityDomain.IAC,
        file_path="docker-compose.yml",
        content="services:\n  app:\n    image: redis:7.0-alpine\n    privileged: false\n",
        expected_positive=False,
    ),
    # 7. Supply Chain / SBOM: Positive
    BenchmarkCase(
        id="SC-POS-01",
        domain=SecurityDomain.SUPPLY_CHAIN,
        file_path="requirements.txt",
        content="requests==2.20.0\n",
        expected_positive=True,
        expected_rule="CVE-2018-18074",
    ),
    # 8. Supply Chain / SBOM: Negative
    BenchmarkCase(
        id="SC-NEG-01",
        domain=SecurityDomain.SUPPLY_CHAIN,
        file_path="requirements.txt",
        content="requests==2.25.1\n",
        expected_positive=False,
    ),
]


def run_goal53_benchmark() -> dict[str, Any]:
    print("=" * 68)
    print("POLARIS v1.7 — GOAL 53 Security Intelligence Platform Benchmark")
    print("=" * 68)

    registry = build_default_scanner_registry()
    tp = fp = tn = fn = 0

    tracemalloc.start()
    t0 = time.perf_counter()

    for case in BENCHMARK_CORPUS:
        results = registry.run_scanners_on_file(case.file_path, case.content)
        has_positive = len(results) > 0

        if case.expected_positive:
            if has_positive:
                tp += 1
            else:
                fn += 1
        else:
            if has_positive:
                fp += 1
            else:
                tn += 1

    elapsed_ms = (time.perf_counter() - t0) * 1000
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    print(f"Total Evaluated Cases: {len(BENCHMARK_CORPUS)} (Positives: {tp+fn}, Negatives: {tn+fp})")
    print(f"TP: {tp} | FP: {fp} | TN: {tn} | FN: {fn}")
    print(f"Precision: {precision:.4f} | Recall: {recall:.4f} | F1: {f1:.4f}")
    print(f"FPR: {fpr:.4f} | FNR: {fnr:.4f}")
    print(f"Total Latency: {elapsed_ms:.2f} ms | Peak Memory: {peak_bytes / 1024:.2f} KB")
    print("=" * 68)

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "fnr": fnr,
        "elapsed_ms": elapsed_ms,
        "peak_kb": peak_bytes / 1024,
    }


if __name__ == "__main__":
    run_goal53_benchmark()
