from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from polaris_server.db import get_connection, run_migrations
from polaris_server.issues_service import get_issue_flow, upsert_issue_occurrence

ROOT = Path(__file__).resolve().parents[2]


class TestCheckpoint03ScannerFlow(unittest.TestCase):
    def test_polaris_scanner_analyze_csharp_taint_flow(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "UserController.cs").write_text(
                "public class UserController {\n  private readonly UserService _svc = new();\n  public string Get(string userId) => _svc.Find(userId);\n}\n",
                encoding="utf-8",
            )
            (tdir / "UserService.cs").write_text(
                "public class UserService {\n  private readonly UserRepository _repo = new();\n  public string Find(string id) => _repo.QueryUser(id);\n}\n",
                encoding="utf-8",
            )
            (tdir / "UserRepository.cs").write_text(
                "public class UserRepository {\n  public string QueryUser(string id) { ExecuteSqlRaw(\"SELECT * FROM Users WHERE Id=\" + id); return \"ok\"; }\n  private void ExecuteSqlRaw(string sql) {}\n}\n",
                encoding="utf-8",
            )
            out_json = tdir / "report.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            res = subprocess.run(
                [sys.executable, "-m", "polaris_scanner.cli", "analyze", "--target", str(tdir), "--project", "cp03-csharp", "--languages", "csharp", "--output", str(out_json)],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            report = json.loads(out_json.read_text(encoding="utf-8"))
            taint_issues = [i for i in report["issues"] if i["ruleId"] == "CS-TAINT-001"]
            self.assertEqual(len(taint_issues), 1)
            self.assertEqual(taint_issues[0]["cwe"], "CWE-89")
            self.assertEqual({s["file"] for s in taint_issues[0]["flowSteps"]}, {"UserController.cs", "UserService.cs", "UserRepository.cs"})

            # Ensure parent project and analysis rows exist (ADR-011 referential integrity)
            run_migrations()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO projects (project_key, name) VALUES (%s, %s) ON CONFLICT (project_key) DO NOTHING",
                        ("cp03-csharp", "Checkpoint 03 C#"),
                    )
                    cur.execute(
                        "INSERT INTO analyses (analysis_id, project_key, status, total_files) VALUES (%s, %s, %s, %s) ON CONFLICT (analysis_id) DO NOTHING",
                        ("manual", "cp03-csharp", "COMPLETED", 3),
                    )
                conn.commit()

            # Persist flow steps via issues_service and query via get_issue_flow
            rec = upsert_issue_occurrence(
                "cp03-csharp",
                "CS-TAINT-001",
                "CRITICAL",
                "VULNERABILITY",
                taint_issues[0]["location"]["file"],
                taint_issues[0]["location"]["startLine"],
                taint_issues[0]["message"],
                "fp-cp03-1",
                cwe="CWE-89",
                flow_steps=taint_issues[0]["flowSteps"],
            )
            flow = get_issue_flow(rec.issue_id)
            self.assertEqual(flow["cwe"], "CWE-89")
            self.assertEqual(len(flow["flow_steps"]), 4)


if __name__ == "__main__":
    unittest.main()
