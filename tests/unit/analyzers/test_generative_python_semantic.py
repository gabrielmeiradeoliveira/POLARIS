import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analyzers" / "python"))

from polaris_python_analyzer import analyze_python_file  # noqa: E402


class TestGenerativePythonSemantic(unittest.TestCase):
    def test_seeded_dead_store_programs(self) -> None:
        rng = random.Random(42)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for idx in range(20):
                has_dead_store = rng.choice([True, False])
                var = f"v_{idx}"
                if has_dead_store:
                    code = (
                        f"def fn_{idx}():\n"
                        f"    {var} = {rng.randint(1, 50)}\n"
                        f"    {var} = {rng.randint(51, 100)}\n"
                        f"    return {var}\n"
                    )
                else:
                    code = (
                        f"def fn_{idx}():\n"
                        f"    {var} = {rng.randint(1, 50)}\n"
                        f"    out = {var} + 1\n"
                        f"    return out\n"
                    )
                p = root / f"gen_{idx}.py"
                p.write_text(code, encoding="utf-8")
                issues, _ = analyze_python_file(p, root)
                dead_issues = [i for i in issues if i["ruleId"] == "PY-SEM-DEAD-001"]
                if has_dead_store:
                    self.assertEqual(len(dead_issues), 1, msg=f"Expected dead store in gen_{idx}.py")
                else:
                    self.assertEqual(len(dead_issues), 0, msg=f"Unexpected dead store in gen_{idx}.py")


if __name__ == "__main__":
    unittest.main()
