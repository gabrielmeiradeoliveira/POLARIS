import json
import sys
import tempfile
import unittest
import urllib.request
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from polaris_scanner.contracts import validate_analysis_result
from polaris_scanner.discovery import discover_files
from polaris_scanner.executor import run_analyzer_subprocess
from polaris_scanner.registry import AnalyzerRegistry


class TestFullE2EPipeline(unittest.TestCase):
    def test_scanner_analyzers_api_postgres_browser(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        registry = AnalyzerRegistry()
        project_key = f"e2e-{uuid.uuid4().hex[:8]}"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("def f(x=[]):\n    return eval('1')\n", encoding="utf-8")
            (root / "App.cs").write_text("class A { string F() { try { return \"x\"; } catch { } return null; } }\n", encoding="utf-8")
            (root / "App.java").write_text("class A { void f() { try { System.out.println(1); } catch (Exception e) {} } }\n", encoding="utf-8")
            (root / "q.sql").write_text("SELECT * FROM t; DELETE FROM t;\n", encoding="utf-8")

            disc = discover_files(root)
            all_issues = []
            for f in disc.files:
                spec = registry.get_by_language(f.language)
                res = run_analyzer_subprocess(
                    [*spec.command, "--project", project_key, "--root", str(root), str(f.absolute_path)],
                    cwd=repo_root,
                )
                self.assertEqual(res.status, "OK")
                self.assertEqual(validate_analysis_result(res.payload), [])
                all_issues.extend(res.payload["issues"])

            self.assertEqual(len(all_issues), 8)

            # Create project in real API -> PostgreSQL
            req_proj = urllib.request.Request(
                "http://127.0.0.1:8000/api/v1/projects",
                data=json.dumps({"projectKey": project_key, "name": f"E2E {project_key}"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_proj, timeout=5) as resp:
                self.assertIn(resp.status, (200, 201))

            # Verify in real Chromium browser
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto("http://127.0.0.1:5173/#/projects", wait_until="networkidle")
                self.assertIn(project_key, page.inner_text("main"))
                browser.close()


if __name__ == "__main__":
    unittest.main()
