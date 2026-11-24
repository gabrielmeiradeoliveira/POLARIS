import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_scanner.contracts import validate_analysis_result
from polaris_scanner.executor import run_analyzer_subprocess
from polaris_scanner.registry import AnalyzerRegistry


class TestJavaAnalyzer(unittest.TestCase):
    def test_javaparser_rules_and_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        spec = AnalyzerRegistry().get_by_language("java")
        self.assertIsNotNone(spec)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            java_file = root / "Sample.java"
            java_file.write_text(
                "public class Sample {\n  public void run() { try { System.out.println(\"hi\"); } catch (Exception e) { } }\n}\n",
                encoding="utf-8",
            )
            res = run_analyzer_subprocess(
                [*spec.command, "--project", "java-test", "--root", str(root), str(java_file)],
                cwd=repo_root,
            )
            self.assertEqual(res.status, "OK", msg=res.error_message or res.stderr)
            self.assertEqual(validate_analysis_result(res.payload), [])
            rule_ids = {i["ruleId"] for i in res.payload["issues"]}
            self.assertEqual(rule_ids, {"JV-SYN-001", "JV-SEM-001", "JV-REL-008"})


if __name__ == "__main__":
    unittest.main()
