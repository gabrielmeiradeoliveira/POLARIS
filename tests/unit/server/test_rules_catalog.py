import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_server.rules_catalog import RULES_CATALOG, query_rules


class TestRulesCatalog(unittest.TestCase):
    def test_catalog_covers_four_languages(self) -> None:
        langs = {r.language for r in RULES_CATALOG}
        self.assertEqual(langs, {"python", "csharp", "java", "sql"})
        self.assertEqual(len(query_rules(language="python")), 2)
        self.assertEqual(len(query_rules(category="SECURITY")), 1)


if __name__ == "__main__":
    unittest.main()
