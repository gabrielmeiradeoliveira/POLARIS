import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analyzers" / "python"))

from polaris_python_analyzer import analyze_python_file  # noqa: E402


class TestMetamorphicPython(unittest.TestCase):
    def _run_on_source(self, source: str) -> list[dict]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "sample.py"
            target.write_text(source, encoding="utf-8")
            issues, _ = analyze_python_file(target, root)
            return issues

    def test_metamorphic_nullability_and_unreachable_preservation(self) -> None:
        base_src = (
            "def process(flag):\n"
            "    user = None\n"
            "    if flag:\n"
            "        user = 'alice'\n"
            "    if user is not None:\n"
            "        return user.upper()\n"
            "    return user.upper()\n"
            "    x = 1\n"
        )
        # Metamorphic transform: rename function, rename variables, add comments
        meta_src = (
            "# Metamorphic variant\n"
            "def handle_request(is_admin):\n"
            "    account = None  # initially null\n"
            "    if is_admin:\n"
            "        account = 'alice'\n"
            "    if account is not None:\n"
            "        return account.upper()\n"
            "    return account.upper()\n"
            "    dead_var = 1\n"
        )
        base_issues = self._run_on_source(base_src)
        meta_issues = self._run_on_source(meta_src)

        base_rules = sorted(i["ruleId"] for i in base_issues)
        meta_rules = sorted(i["ruleId"] for i in meta_issues)
        self.assertIn("PY-SEM-NULL-001", base_rules)
        self.assertIn("PY-SEM-UNREACH-001", base_rules)
        self.assertEqual(base_rules, meta_rules)

    def test_safe_guarded_nullability_has_zero_null_issues(self) -> None:
        safe_src = (
            "def process(flag):\n"
            "    user = None\n"
            "    if flag:\n"
            "        user = 'alice'\n"
            "    if user is not None:\n"
            "        return user.upper()\n"
            "    return 'ANON'\n"
        )
        issues = self._run_on_source(safe_src)
        null_issues = [i for i in issues if i["ruleId"] == "PY-SEM-NULL-001"]
        self.assertEqual(null_issues, [])


if __name__ == "__main__":
    unittest.main()
