import unittest

from analyzers.sql.semantic_engine import resolve_sql_semantics


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
