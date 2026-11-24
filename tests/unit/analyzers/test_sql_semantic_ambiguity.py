import importlib.util
import unittest
from pathlib import Path

_SQL_SEMANTIC_PATH = Path(__file__).resolve().parents[3] / "analyzers" / "sql" / "semantic_engine.py"
_SPEC = importlib.util.spec_from_file_location("polaris_sql_semantic_engine", _SQL_SEMANTIC_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
resolve_sql_semantics = _MOD.resolve_sql_semantics


class TestSqlSemanticAmbiguity(unittest.TestCase):
    def test_detects_ambiguous_unqualified_column_in_join(self):
        schema = {
            "users": ["id", "name"],
            "orders": ["id", "user_id", "total"],
        }
        sql = "SELECT id, name FROM users u JOIN orders o ON u.id = o.user_id"
        res = resolve_sql_semantics(sql, schema, dialect="postgres")
        self.assertIn("id", res["ambiguous_columns"])
        self.assertEqual(res["unknown_columns"], [])


if __name__ == "__main__":
    unittest.main()
