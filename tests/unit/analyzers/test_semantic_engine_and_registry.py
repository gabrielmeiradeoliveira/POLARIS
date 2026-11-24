import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analyzers" / "python"))

from security_models import SecurityModelRegistry, SinkSpec, SourceSpec  # noqa: E402
from semantic_engine import (  # noqa: E402
    ConstantPropagationAnalysis,
    ControlFlowGraph,
    NullabilityAnalysis,
)


class TestSemanticEngineAndRegistry(unittest.TestCase):
    def test_cfg_and_constant_propagation_branch_merge(self) -> None:
        code = """
def f(flag):
    x = 10
    y = 20
    if flag:
        z = x + 5
        w = 1
    else:
        z = 15
        w = 2
    return z + w
"""
        func = ast.parse(code).body[0]
        cfg = ControlFlowGraph.from_function_ast(func)
        self.assertGreaterEqual(len(cfg.blocks), 5)

        in_states, _ = ConstantPropagationAnalysis.analyze(func)
        exit_state = in_states[cfg.exit_id]
        # z is 15 on both branches -> CONST 15; w differs (1 vs 2) -> NAC
        self.assertEqual(exit_state["z"], ("CONST", 15))
        self.assertEqual(exit_state["w"][0], "NAC")

    def test_nullability_branch_refinement(self) -> None:
        code = """
def g(cond):
    user = None
    if cond:
        user = "alice"
    if user is not None:
        a = user.upper()
    else:
        b = user.upper()
"""
        func = ast.parse(code).body[0]
        findings = NullabilityAnalysis.find_null_dereferences(func)
        # Only the else branch (line 8: b = user.upper()) should be flagged as NULL
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["variable"], "user")
        self.assertEqual(findings[0]["state"], NullabilityAnalysis.NULL)
        self.assertEqual(findings[0]["line"], 9)

    def test_security_model_registry_default_and_json_load(self) -> None:
        reg = SecurityModelRegistry.default_registry()
        self.assertTrue(reg.is_sink("python", "sqlite3.Cursor.execute"))
        self.assertTrue(reg.is_sanitizer("python", "shlex.quote", "CWE-78"))
        self.assertFalse(reg.is_sanitizer("python", "shlex.quote", "CWE-89"))

        with tempfile.TemporaryDirectory() as tmp:
            model_file = Path(tmp) / "custom_models.json"
            model_file.write_text(
                json.dumps(
                    {
                        "sources": [{"language": "python", "symbol": "custom.get_input"}],
                        "sinks": [{"language": "python", "symbol": "custom.exec_sql", "cwe": "CWE-89"}],
                    }
                ),
                encoding="utf-8",
            )
            reg.load_json(model_file)
            self.assertIsNotNone(reg.is_sink("python", "custom.exec_sql"))
            self.assertTrue(any(s.symbol == "custom.get_input" for s in reg.get_sources("python")))


if __name__ == "__main__":
    unittest.main()
