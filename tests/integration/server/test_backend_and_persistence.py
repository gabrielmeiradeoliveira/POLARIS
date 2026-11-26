import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_server.config import ServerConfig
from polaris_server.db import get_connection, run_migrations


class TestBackendAndPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 8096
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        venv_py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
        full_env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        cls.srv = subprocess.Popen(
            [str(venv_py), "-m", "uvicorn", "polaris_server.api:app", "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=str(REPO_ROOT),
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{cls.base_url}/health/live", timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:
                time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(timeout=5)

    def test_01_liveness_readiness_version_and_request_id(self):
        with urllib.request.urlopen(f"{self.base_url}/health/live") as r:
            self.assertEqual(r.status, 200)
            self.assertTrue(r.headers.get("X-Request-ID"))
            self.assertEqual(json.loads(r.read().decode("utf-8"))["status"], "ALIVE")

        with urllib.request.urlopen(f"{self.base_url}/health/ready") as r:
            self.assertEqual(r.status, 200)
            self.assertEqual(json.loads(r.read().decode("utf-8"))["status"], "READY")

        with urllib.request.urlopen(f"{self.base_url}/api/v1/version") as r:
            self.assertEqual(r.status, 200)
            ver = json.loads(r.read().decode("utf-8"))
            self.assertEqual(ver["service"], "polaris-server")

    def test_02_readiness_fails_when_db_unavailable(self):
        bad_port = 8097
        venv_py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
        full_env = {
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT / "src"),
            "POLARIS_PG_DSN": "postgresql://polaris:wrong@127.0.0.1:5999/none",
        }
        proc = subprocess.Popen(
            [str(venv_py), "-m", "uvicorn", "polaris_server.api:app", "--host", "127.0.0.1", "--port", str(bad_port)],
            cwd=str(REPO_ROOT),
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            for _ in range(25):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{bad_port}/health/live", timeout=1)
                    break
                except Exception:
                    time.sleep(0.2)
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(f"http://127.0.0.1:{bad_port}/health/ready", timeout=3)
            self.assertEqual(ctx.exception.code, 503)
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_03_invalid_json_and_payload_limit(self):
        req = urllib.request.Request(
            f"{self.base_url}/api/v1/projects",
            data=b"{bad",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 422)

        req_big = urllib.request.Request(
            f"{self.base_url}/api/v1/analyses",
            data=b"x" * (6 * 1024 * 1024),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req_big)
            self.fail("Esperado erro 413 ou conexão abortada pelo limite de payload.")
        except urllib.error.HTTPError as ctx2:
            self.assertEqual(ctx2.code, 413)
        except ConnectionAbortedError:
            pass

    def test_05_pr_ai_summary_http_200_and_token_fields(self):
        body = json.dumps(
            {
                "issues": [
                    {"ruleId": "PY-SEC-001", "severity": "CRITICAL", "file_path": "a.py", "start_line": 10, "message": "cmd injection"}
                ]
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/prs/PR-HTTP-1/ai-summary",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            self.assertEqual(r.status, 200)
            payload = json.loads(r.read().decode("utf-8"))
        for field in (
            "estimated_tokens",
            "actual_input_tokens",
            "actual_output_tokens",
            "actual_total_tokens",
            "saved_tokens",
        ):
            self.assertIn(field, payload)

    def test_04_migrations_idempotent_and_transactions_rollback(self):
        run_migrations(ServerConfig())
        applied_again = run_migrations(ServerConfig())
        self.assertEqual(applied_again, [])

        with get_connection(ServerConfig()) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO projects (project_key, name) VALUES ('rb-test', 'RB') ON CONFLICT DO NOTHING;")
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM projects WHERE project_key = 'rb-test';")
                self.assertIsNone(cur.fetchone())


if __name__ == "__main__":
    unittest.main(verbosity=2)
