from __future__ import annotations

import ast
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "python"))

from polaris_scanner.cache import IncrementalScanCache, compute_file_sha256
from polaris_scanner.contracts import validate_analysis_result
from polaris_scanner.runner import WorkerTask, run_workers_parallel
from polaris_scanner.executor import ExecutionResult
from polaris_scanner.registry import AnalyzerRegistry
from polaris_server.domain_core import evaluate_quality_gate
from taint_engine import analyze_python_taint, has_taint_tokens


class TestEngineBenchmarkAndCalibration(unittest.TestCase):
    def test_cold_vs_warm_incremental_cache_and_fast_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files: list[Path] = []
            # 200+ polyglot-style files (Python)
            for i in range(210):
                p = root / f"mod_{i}.py"
                if i % 50 == 0:
                    p.write_text(
                        "import os\ndef run(cmd):\n    x = input()\n    os.system(x)\n",
                        encoding="utf-8",
                    )
                else:
                    p.write_text(
                        f"def add_{i}(a: int, b: int) -> int:\n    return a + b\n",
                        encoding="utf-8",
                    )
                files.append(p)

            cache_path = root / ".polaris" / "cache.sqlite"
            t0 = time.perf_counter()
            with IncrementalScanCache(cache_path) as cache:
                for p in files:
                    src = p.read_text(encoding="utf-8")
                    tree = ast.parse(src)
                    findings = analyze_python_taint(tree, source_code=src)
                    sha = compute_file_sha256(p)
                    cache.put(
                        file_path=p.name,
                        file_sha256=sha,
                        rule_profile_hash="prof-v1",
                        worker_version="2.6.0",
                        issues=[{"ruleId": f.rule_id, "confidence": f.confidence} for f in findings],
                    )
                cache.commit()
            cold_ms = (time.perf_counter() - t0) * 1000.0

            # Modify 5 files
            for idx in range(5):
                files[idx].write_text(
                    f"def updated_{idx}(x: int) -> int:\n    return x * 2\n",
                    encoding="utf-8",
                )

            # Warm incremental run
            t1 = time.perf_counter()
            hits = 0
            misses = 0
            with IncrementalScanCache(cache_path) as cache:
                for p in files:
                    sha = compute_file_sha256(p)
                    cached = cache.get(
                        file_sha256=sha,
                        rule_profile_hash="prof-v1",
                        worker_version="2.6.0",
                    )
                    if cached is not None:
                        hits += 1
                    else:
                        misses += 1
                        src = p.read_text(encoding="utf-8")
                        tree = ast.parse(src)
                        findings = analyze_python_taint(tree, source_code=src)
                        cache.put(
                            file_path=p.name,
                            file_sha256=sha,
                            rule_profile_hash="prof-v1",
                            worker_version="2.6.0",
                            issues=[{"ruleId": f.rule_id, "confidence": f.confidence} for f in findings],
                        )
                cache.commit()
            warm_ms = (time.perf_counter() - t1) * 1000.0

            self.assertEqual(hits, 205)
            self.assertEqual(misses, 5)
            self.assertLess(warm_ms, 500.0, f"Warm run took {warm_ms:.2f}ms (expected < 500ms)")
            self.assertGreater(cold_ms, 0.0)

    def test_zero_false_positives_on_sanitized_fixtures(self) -> None:
        clean_samples = [
            "import shlex, os\ndef safe(u):\n    q = shlex.quote(input())\n    os.system(q)\n",
            "def pure_math(a, b):\n    return (a + b) * 2\n",
        ]
        for code in clean_samples:
            tree = ast.parse(code)
            findings = analyze_python_taint(tree, source_code=code)
            self.assertEqual(findings, [])
        self.assertFalse(has_taint_tokens("def pure_math(a, b):\n    return a + b\n"))

    def test_confidence_contract_and_quality_gate_min_confidence(self) -> None:
        payload = {
            "schemaVersion": "1.0.0",
            "analysisId": "a1",
            "projectKey": "p1",
            "branch": "main",
            "analyzer": {"id": "polaris-python-analyzer", "version": "2.6.0"},
            "status": "COMPLETED",
            "totalFiles": 1,
            "diagnostics": [],
            "issues": [
                {
                    "ruleId": "python:PY-SEC-001",
                    "language": "python",
                    "severity": "CRITICAL",
                    "confidence": "HIGH",
                    "location": {"file": "app.py", "startLine": 10},
                    "message": "SQL Injection",
                }
            ],
        }
        self.assertEqual(validate_analysis_result(payload), [])

        issues = [
            {"type": "VULNERABILITY", "severity": "CRITICAL", "confidence": "LOW"},
            {"type": "VULNERABILITY", "severity": "CRITICAL", "confidence": "MEDIUM"},
        ]
        res = evaluate_quality_gate(
            {"vulnerabilities": 2},
            [{"metric": "vulnerabilities", "operator": "GT", "threshold": 0, "min_confidence": "HIGH"}],
            issues=issues,
        )
        self.assertEqual(res["status"], "PASSED")
        self.assertEqual(res["conditions"][0]["value"], 0.0)

    def test_parallel_worker_runner(self) -> None:
        reg = AnalyzerRegistry()
        tasks = [
            WorkerTask(language="python", spec=reg.get_by_language("python"), files=["a.py"]),
            WorkerTask(language="sql", spec=reg.get_by_language("sql"), files=["b.sql"]),
        ]

        def fake_exec(cmd, **_kwargs):
            return ExecutionResult(status="OK", exit_code=0, stdout="{}", stderr="", payload={"ok": True})

        outcomes = run_workers_parallel(
            tasks,
            project_key="p1",
            branch="main",
            target_dir=Path("."),
            repo_root=Path("."),
            timeout_seconds=10,
            max_workers=2,
            executor_fn=fake_exec,
        )
        self.assertEqual([o.language for o in outcomes], ["python", "sql"])


if __name__ == "__main__":
    unittest.main()
