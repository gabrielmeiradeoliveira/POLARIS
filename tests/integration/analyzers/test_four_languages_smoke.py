import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_scanner.contracts import validate_analysis_result
from polaris_scanner.discovery import discover_files
from polaris_scanner.executor import run_analyzer_subprocess
from polaris_scanner.registry import AnalyzerRegistry


class TestFourLanguagesSmoke(unittest.TestCase):
    def test_smoke_four_languages_and_determinism(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        registry = AnalyzerRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("def f(x=[]):\n    return eval('1')\n", encoding="utf-8")
            (root / "App.cs").write_text("class A { string F() { try { return \"x\"; } catch { } return null; } }\n", encoding="utf-8")
            (root / "App.java").write_text("class A { void f() { try { System.out.println(1); } catch (Exception e) {} } }\n", encoding="utf-8")
            (root / "q.sql").write_text("SELECT * FROM t; DELETE FROM t;\n", encoding="utf-8")

            discovery = discover_files(root)
            self.assertEqual(len(discovery.files), 4)

            def run_once() -> list[dict]:
                all_issues = []
                for f in discovery.files:
                    spec = registry.get_by_language(f.language)
                    res = run_analyzer_subprocess(
                        [*spec.command, "--project", "smoke-4", "--root", str(root), str(f.absolute_path)],
                        cwd=repo_root,
                    )
                    self.assertEqual(res.status, "OK", msg=f"{f.language}: {res.error_message}")
                    self.assertEqual(validate_analysis_result(res.payload), [])
                    all_issues.extend(res.payload["issues"])
                return all_issues

            first = run_once()
            second = run_once()
            self.assertEqual(first, second)
            self.assertEqual(len(first), 9)


if __name__ == "__main__":
    unittest.main()
