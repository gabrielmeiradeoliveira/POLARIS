from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestMutationAudit(unittest.TestCase):
    def test_mutation_disabling_rule_is_detected(self) -> None:
        py_rules_src = (ROOT / "analyzers" / "python" / "rules_engine.py").read_text(encoding="utf-8")
        mutated_src = py_rules_src.replace(
            'def _check_bare_except(tree: ast.AST, _src: str) -> list[tuple[int, str]]:\n    return [(n.lineno, "Bare except clause") for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and n.type is None]',
            'def _check_bare_except(tree: ast.AST, _src: str) -> list[tuple[int, str]]:\n    return []',
        )
        self.assertNotEqual(py_rules_src, mutated_src)

        with tempfile.TemporaryDirectory() as td:
            mut_path = Path(td) / "rules_engine_mut.py"
            mut_path.write_text(mutated_src, encoding="utf-8")
            spec = importlib.util.spec_from_file_location("mut_py_rules", mut_path)
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            rule = next(r for r in mod.PYTHON_RULES if r.rule_id == "PY-REL-001")
            import ast
            tree = ast.parse("try:\n    x = 1\nexcept:\n    pass\n")
            self.assertEqual(rule.check(tree, ""), [])


if __name__ == "__main__":
    unittest.main()
