import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_scanner.contracts import validate_analysis_result
from polaris_scanner.executor import run_analyzer_subprocess
from polaris_scanner.registry import AnalyzerRegistry


class TestCSharpAnalyzer(unittest.TestCase):
    def test_roslyn_rules_and_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        spec = AnalyzerRegistry().get_by_language("csharp")
        self.assertIsNotNone(spec)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cs_file = root / "Sample.cs"
            cs_file.write_text(
                "using System;\nclass Sample {\n  string Get() { try { return \"ok\"; } catch (Exception) { } return null; }\n}\n",
                encoding="utf-8",
            )
            res = run_analyzer_subprocess(
                [*spec.command, "--project", "cs-test", "--root", str(root), str(cs_file)],
                cwd=repo_root,
            )
            self.assertEqual(res.status, "OK", msg=res.error_message or res.stderr)
            self.assertEqual(validate_analysis_result(res.payload), [])
            rule_ids = {i["ruleId"] for i in res.payload["issues"]}
            self.assertEqual(rule_ids, {"CS-SYN-001", "CS-SEM-001"})


if __name__ == "__main__":
    unittest.main()
