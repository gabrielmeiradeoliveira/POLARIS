import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "analyzers" / "sql"))

from polaris_sql_analyzer import SUPPORTED_DIALECTS, analyze_sql_file


class TestSqlAnalyzer(unittest.TestCase):
    def test_rules_and_dialects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad.sql"
            bad.write_text("SELECT * FROM users;\nDELETE FROM users;\n", encoding="utf-8")
            for dialect in SUPPORTED_DIALECTS:
                issues, diags = analyze_sql_file(bad, root, dialect=dialect)
                self.assertEqual(diags, [])
                self.assertEqual({i["ruleId"] for i in issues}, {"SQL-SYN-001", "SQL-CTX-001"})

            clean = root / "clean.sql"
            clean.write_text("SELECT id, name FROM users WHERE active = 1;", encoding="utf-8")
            issues_c, _ = analyze_sql_file(clean, root, dialect="postgres")
            self.assertEqual(issues_c, [])


if __name__ == "__main__":
    unittest.main()
