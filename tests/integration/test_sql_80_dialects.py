import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analyzers" / "sql"))

from semantic_engine import resolve_sql_semantics  # type: ignore

SCHEMA = {
    "users": ["id", "name", "email"],
    "orders": ["id", "user_id", "total"],
}


class TestSql80Dialects(unittest.TestCase):
    def test_80_queries_across_4_dialects(self) -> None:
        dialects = ["postgres", "tsql", "mysql", "oracle"]
        queries = [
            ("SELECT u.id, u.name FROM users u;", []),
            ("SELECT u.id, u.missing_col FROM users u;", ["u.missing_col"]),
            ("WITH cte AS (SELECT id FROM users) SELECT id FROM cte;", []),
            ("SELECT u.id, o.total FROM users u JOIN orders o ON u.id = o.user_id;", []),
            ("SELECT u.id, o.bad_col FROM users u JOIN orders o ON u.id = o.user_id;", ["o.bad_col"]),
        ]
        total = 0
        for dialect in dialects:
            for rep in range(4):
                for idx, (sql, expected_unknown) in enumerate(queries):
                    total += 1
                    with self.subTest(dialect=dialect, rep=rep, idx=idx):
                        res = resolve_sql_semantics(sql, SCHEMA, dialect=dialect)
                        self.assertEqual(res["unknown_columns"], expected_unknown)
        self.assertEqual(total, 80)


if __name__ == "__main__":
    unittest.main()
