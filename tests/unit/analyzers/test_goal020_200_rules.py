from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

import sqlglot

from polaris_server.rule_metrics import RuleEvalCase, compute_rule_metrics

_py_spec = importlib.util.spec_from_file_location("py_rules_engine", Path(__file__).resolve().parents[3] / "analyzers" / "python" / "rules_engine.py")
assert _py_spec and _py_spec.loader
_py_mod = importlib.util.module_from_spec(_py_spec)
sys.modules[_py_spec.name] = _py_mod
_py_spec.loader.exec_module(_py_mod)
PYTHON_RULES = _py_mod.PYTHON_RULES

_sql_spec = importlib.util.spec_from_file_location("sql_rules_engine", Path(__file__).resolve().parents[3] / "analyzers" / "sql" / "rules_engine.py")
assert _sql_spec and _sql_spec.loader
_sql_mod = importlib.util.module_from_spec(_sql_spec)
sys.modules[_sql_spec.name] = _sql_mod
_sql_spec.loader.exec_module(_sql_mod)
SQL_RULES = _sql_mod.SQL_RULES


class TestGoal020Rules200(unittest.TestCase):
    def test_python_60_rules_executable(self) -> None:
        self.assertGreaterEqual(len(PYTHON_RULES), 60)
        clean_tree = ast.parse("def add(a: int, b: int) -> int:\n    return a + b\n")
        cases = []
        for r in PYTHON_RULES:
            # Negative case on clean code
            findings = r.check(clean_tree, "")
            cases.append(RuleEvalCase(r.rule_id, False, len(findings) > 0))
        metrics = compute_rule_metrics(cases)
        self.assertEqual(len(metrics), len(PYTHON_RULES))
        for rid, m in metrics.items():
            self.assertEqual(m["fp"], 0, msg=f"Unexpected FP on clean code for {rid}")

    def test_sql_20_rules_executable(self) -> None:
        self.assertGreaterEqual(len(SQL_RULES), 20)
        clean_stmt = sqlglot.parse_one("SELECT id, name FROM users WHERE active = 1", read="postgres")
        cases = []
        for r in SQL_RULES:
            finding = r.check(clean_stmt)
            cases.append(RuleEvalCase(r.rule_id, False, finding is not None))
        metrics = compute_rule_metrics(cases)
        self.assertEqual(len(metrics), len(SQL_RULES))
        for rid, m in metrics.items():
            self.assertEqual(m["fp"], 0, msg=f"Unexpected FP on clean SQL for {rid}")

    def test_csharp_and_java_artifacts_compiled(self) -> None:
        root = Path(__file__).resolve().parents[3]
        self.assertTrue((root / "analyzers" / "csharp" / "bin" / "Release" / "net10.0" / "PolarisCSharpAnalyzer.dll").exists())
        self.assertTrue((root / "analyzers" / "java" / "target" / "classes" / "com" / "polaris" / "analyzer" / "JavaRulesEngine.class").exists())


if __name__ == "__main__":
    unittest.main()
