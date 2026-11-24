import json
import os
import statistics
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import psutil

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PY = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
BACKEND_APP = "poc.goal-003-r3.backend.app:app"

import sys
sys.path.insert(0, str(REPO_ROOT / "poc" / "goal-003-r3" / "scanner"))
from scanner_r3 import run_scanner, submit_to_backend


class TestGoal003R3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 8091
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.srv_proc = subprocess.Popen(
            [str(VENV_PY), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=str(REPO_ROOT / "poc" / "goal-003-r3" / "backend"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{cls.base_url}/api/v1/health", timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.srv_proc.terminate()
        cls.srv_proc.wait(timeout=5)

    def test_01_vertical_integration_and_isolation(self):
        corpus = REPO_ROOT / "poc" / "goal-003-r2" / "corpus"
        report = run_scanner(corpus, project_key="demo-r3")
        self.assertEqual(report["totalFiles"], 8)
        self.assertGreaterEqual(len(report["issues"]), 20)

        res = submit_to_backend(self.base_url, report)
        self.assertEqual(res["persistedIssues"], len(report["issues"]))

        with urllib.request.urlopen(f"{self.base_url}/api/v1/projects/demo-r3/issues") as r:
            data = json.loads(r.read().decode("utf-8"))
            self.assertEqual(data["projectKey"], "demo-r3")
            self.assertEqual(len(data["issues"]), len(report["issues"]))

        # Isolamento: outro projeto deve retornar EMPTY
        with urllib.request.urlopen(f"{self.base_url}/api/v1/projects/outro-proj/issues") as r:
            empty_data = json.loads(r.read().decode("utf-8"))
            self.assertEqual(empty_data["status"], "EMPTY")
            self.assertEqual(len(empty_data["issues"]), 0)

    def test_02_security_invalid_json_and_sqli_project_key(self):
        req = urllib.request.Request(
            f"{self.base_url}/api/v1/analyses",
            data=b"{bad-json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 422)

        bad_payload = json.dumps({
            "schemaVersion": "1.0.0",
            "analysisId": "sec-1",
            "projectKey": "'; DROP TABLE r3_issues;--",
            "status": "COMPLETED",
            "totalFiles": 0,
            "issues": [],
        }).encode("utf-8")
        req2 = urllib.request.Request(
            f"{self.base_url}/api/v1/analyses",
            data=bad_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx2:
            urllib.request.urlopen(req2)
        self.assertEqual(ctx2.exception.code, 422)

    def test_03_scanner_invalid_file_and_benchmark_rss(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_py = Path(tmpdir) / "broken file.py"
            bad_py.write_text("def broken(:\n", encoding="utf-8")
            rep = run_scanner(Path(tmpdir), project_key="bad-proj")
            self.assertEqual(rep["status"], "COMPLETED_WITH_WARNINGS")

        # Benchmark 3 execucoes com RSS real
        corpus = REPO_ROOT / "poc" / "goal-003-r2" / "corpus"
        times = []
        rss_mb = []
        proc = psutil.Process(os.getpid())
        for _ in range(3):
            t0 = time.perf_counter()
            run_scanner(corpus, project_key="bench-r3")
            times.append(time.perf_counter() - t0)
            rss_mb.append(proc.memory_info().rss / (1024 * 1024))
        print(f"\nBENCHMARK_R3_MEDIAN_SEC={statistics.median(times):.4f} RSS_MB={max(rss_mb):.2f}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
