import json
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_scanner.cli import discover_source_files


class TestPolarisFoundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 8095
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        venv_py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
        env = {"PYTHONPATH": str(REPO_ROOT / "src")}
        import os
        full_env = {**os.environ, **env}
        cls.srv = subprocess.Popen(
            [str(venv_py), "-m", "uvicorn", "polaris_server.api:app", "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=str(REPO_ROOT),
            env=full_env,
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
        cls.srv.terminate()
        cls.srv.wait(timeout=5)

    def test_scanner_discovery_and_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            (root / "b.cs").write_text("class B {}\n", encoding="utf-8")
            (root / "c.txt").write_text("ignored\n", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "skip.py").write_text("x = 2\n", encoding="utf-8")
            found = discover_source_files(root)
            rels = [r[1] for r in found]
            self.assertEqual(rels, ["a.py", "b.cs"])

    def test_server_projects_and_analyses_postgresql(self):
        proj_key = f"proj-{int(time.time())}"
        req = urllib.request.Request(
            f"{self.base_url}/api/v1/projects",
            data=json.dumps({"projectKey": proj_key, "name": "Projeto Teste"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.status, 201)

        # Duplicado -> 409
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 409)

        # Analise valida -> 201
        anl_payload = {
            "schemaVersion": "1.0.0",
            "analysisId": f"anl-{proj_key}",
            "projectKey": proj_key,
            "branch": "main",
            "status": "COMPLETED",
            "totalFiles": 1,
            "issues": [
                {
                    "ruleId": "PY-R001",
                    "language": "python",
                    "severity": "HIGH",
                    "location": {"file": "a.py", "startLine": 1},
                    "message": "Teste",
                }
            ],
        }
        req_anl = urllib.request.Request(
            f"{self.base_url}/api/v1/analyses",
            data=json.dumps(anl_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_anl) as r:
            self.assertEqual(r.status, 201)

        with urllib.request.urlopen(f"{self.base_url}/api/v1/projects/{proj_key}/issues") as r:
            data = json.loads(r.read().decode("utf-8"))
            self.assertEqual(len(data["issues"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
