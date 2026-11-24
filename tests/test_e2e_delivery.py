import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path

from polaris_scanner.cli import main as scanner_main


@unittest.skipUnless(os.getenv("POLARIS_TEST_PG") == "1", "Set POLARIS_TEST_PG=1 to run PostgreSQL E2E tests")
class TestE2EDelivery(unittest.TestCase):
    def test_full_delivery_journey(self):
        from polaris_server.api import AnalysisInput, IssueInput, LocationModel, ProjectCreate, create_analysis, create_project, get_project_overview

        project_key = f"e2e-{uuid.uuid4().hex[:8]}"
        create_project(ProjectCreate(projectKey=project_key, name="E2E Delivery Project"))

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "app.py").write_text("def run(x):\n    return eval(x)\n", encoding="utf-8")
            (repo / "query.sql").write_text("SELECT * FROM users;\n", encoding="utf-8")
            (repo / "Program.cs").write_text("class Program { static void Main() {} }\n", encoding="utf-8")
            (repo / "Main.java").write_text("public class Main { public static void main(String[] args) {} }\n", encoding="utf-8")

            # 1. Independent scanner — First scan
            out1 = repo / "report1.json"
            self.assertEqual(scanner_main(["analyze", "--target", str(repo), "--project", project_key, "--output", str(out1)]), 0)
            rep1 = json.loads(out1.read_text(encoding="utf-8"))
            anl1_id = f"e2e-1-{uuid.uuid4().hex[:8]}"
            res1 = create_analysis(
                AnalysisInput(
                    schemaVersion="1.0.0",
                    analysisId=anl1_id,
                    projectKey=project_key,
                    branch="main",
                    status="COMPLETED",
                    totalFiles=int(rep1.get("totalFiles", 4)),
                    issues=[
                        IssueInput(
                            ruleId=str(i.get("ruleId", "UNKNOWN")),
                            language=str(i.get("language", "unknown")),
                            severity=str(i.get("severity", "MAJOR")),
                            location=LocationModel(
                                file=str((i.get("location") or {}).get("file", "")),
                                startLine=int((i.get("location") or {}).get("startLine", 0)),
                            ),
                            message=str(i.get("message", "")),
                        )
                        for i in rep1.get("issues", [])
                    ],
                )
            )
            self.assertEqual(res1["status"], "COMPLETED")

            ov1 = get_project_overview(project_key)
            self.assertGreaterEqual(len(ov1["issues"]), 1)

            # 2. Fix Python issue in test repo
            (repo / "app.py").write_text("def run(x):\n    return int(x)\n", encoding="utf-8")

            # 3. Independent scanner — Second scan
            out2 = repo / "report2.json"
            self.assertEqual(scanner_main(["analyze", "--target", str(repo), "--project", project_key, "--output", str(out2)]), 0)
            rep2 = json.loads(out2.read_text(encoding="utf-8"))
            anl2_id = f"e2e-2-{uuid.uuid4().hex[:8]}"
            create_analysis(
                AnalysisInput(
                    schemaVersion="1.0.0",
                    analysisId=anl2_id,
                    projectKey=project_key,
                    branch="main",
                    status="COMPLETED",
                    totalFiles=int(rep2.get("totalFiles", 4)),
                    issues=[
                        IssueInput(
                            ruleId=str(i.get("ruleId", "UNKNOWN")),
                            language=str(i.get("language", "unknown")),
                            severity=str(i.get("severity", "MAJOR")),
                            location=LocationModel(
                                file=str((i.get("location") or {}).get("file", "")),
                                startLine=int((i.get("location") or {}).get("startLine", 0)),
                            ),
                            message=str(i.get("message", "")),
                        )
                        for i in rep2.get("issues", [])
                    ],
                )
            )

            ov2 = get_project_overview(project_key)
            self.assertEqual(ov2["latestAnalysis"]["analysisId"], anl2_id)
            self.assertLess(len(ov2["issues"]), len(ov1["issues"]))
