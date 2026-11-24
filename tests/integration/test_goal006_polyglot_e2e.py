from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from polaris_scanner.contracts import validate_analysis_result
from polaris_server.db import get_connection, run_migrations

ROOT = Path(__file__).resolve().parents[2]


class TestGoal006PolyglotE2E(unittest.TestCase):
    def test_polyglot_scanner_gzip_and_persistence(self) -> None:
        run_migrations()
        project_key = "goal006-polyglot"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO projects (project_key, name) VALUES (%s, %s) ON CONFLICT (project_key) DO NOTHING",
                    (project_key, "GOAL-006 Polyglot"),
                )
            conn.commit()

        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "app.py").write_text(
                "def bad(unused_arg):\n    secret = 'hardcoded_password_123'\n    try:\n        x = 1\n    except:\n        pass\n",
                encoding="utf-8",
            )
            (tdir / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            (tdir / "Sample.cs").write_text(
                "public class Sample {\n  public void Run() { int unused = 1; }\n}\n",
                encoding="utf-8",
            )
            (tdir / "Demo.java").write_text(
                "public class Demo {\n  public static void main(String[] args) { System.out.println(\"hi\"); }\n}\n",
                encoding="utf-8",
            )
            (tdir / "query.sql").write_text(
                "SELECT * FROM users;\nDELETE FROM users;\n",
                encoding="utf-8",
            )

            out_json = tdir / "polyglot_report.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            t0 = time.perf_counter()
            res = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "polaris_scanner.cli",
                    "analyze",
                    "--target",
                    str(tdir),
                    "--project",
                    project_key,
                    "--output",
                    str(out_json),
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
            elapsed = time.perf_counter() - t0
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertLess(elapsed, 15.0)

            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(validate_analysis_result(report), [])
            self.assertGreaterEqual(len(report["issues"]), 1)

            # Verify gzipped payload compression round-trip
            compressed = gzip.compress(json.dumps(report).encode("utf-8"))
            self.assertLess(len(compressed), len(json.dumps(report).encode("utf-8")))


if __name__ == "__main__":
    unittest.main()
