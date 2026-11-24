import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


class TestScannerAnalyzeCommand(unittest.TestCase):
    def test_analyze_offline_and_connected_four_languages(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo_root / "src")
        project_key = f"g5-{uuid.uuid4().hex[:8]}"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("def f(x=[]):\n    return eval('1')\n", encoding="utf-8")
            (root / "App.cs").write_text("class A { string F() { try { return \"x\"; } catch { } return null; } }\n", encoding="utf-8")
            (root / "App.java").write_text("class A { void f() { try { System.out.println(1); } catch (Exception e) {} } }\n", encoding="utf-8")
            (root / "q.sql").write_text("SELECT * FROM t; DELETE FROM t;\n", encoding="utf-8")
            out_file = root / "report.json"

            res = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "polaris_scanner.cli",
                    "analyze",
                    "--target",
                    str(root),
                    "--project",
                    project_key,
                    "--output",
                    str(out_file),
                    "--server",
                    "http://127.0.0.1:8000",
                ],
                cwd=str(repo_root),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                shell=False,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            report = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(report["totalFiles"], 4)
            self.assertEqual(len(report["issues"]), 8)
            self.assertTrue(all("fingerprint" in i and len(i["fingerprint"]) == 64 for i in report["issues"]))


if __name__ == "__main__":
    unittest.main()
