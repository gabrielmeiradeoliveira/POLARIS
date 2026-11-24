import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "analyzers" / "python"))

from polaris_python_analyzer import analyze_python_file


class TestPythonAnalyzer(unittest.TestCase):
    def test_rules_and_syntax_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad.py"
            bad.write_text("def f(x=[]):\n    return eval('1+1')\n", encoding="utf-8")
            issues, diags = analyze_python_file(bad, root)
            self.assertEqual(diags, [])
            rule_ids = {i["ruleId"] for i in issues}
            self.assertEqual(rule_ids, {"PY-SYN-001", "PY-SEM-001"})

            clean = root / "clean.py"
            clean.write_text("def ok(x=None):\n    return 42\n", encoding="utf-8")
            issues_c, diags_c = analyze_python_file(clean, root)
            self.assertEqual(issues_c, [])
            self.assertEqual(diags_c, [])

            invalid = root / "broken.py"
            invalid.write_text("def broken(:\n", encoding="utf-8")
            _, diags_i = analyze_python_file(invalid, root)
            self.assertEqual(len(diags_i), 1)
            self.assertEqual(diags_i[0]["type"], "syntax_error")


if __name__ == "__main__":
    unittest.main()
