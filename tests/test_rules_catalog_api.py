import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "validation"))

from polaris_server.rules_router import get_rule, list_rules  # noqa: E402
import validate_rules as vr  # noqa: E402


class TestRulesCatalogAPI(unittest.TestCase):
    def test_inventory_matches_api_exactly(self):
        inv = vr.load_inventory()
        api_res = list_rules(limit=500)
        self.assertEqual(api_res["total"], len(inv))
        self.assertEqual(len(api_res["items"]), len(inv))
        inv_ids = {r["ruleId"] for r in inv}
        api_ids = {r["ruleId"] for r in api_res["items"]}
        self.assertEqual(inv_ids, api_ids)

        sample = get_rule("PY-SYN-001")
        self.assertEqual(sample["ruleId"], "PY-SYN-001")
        self.assertIn("validationStatus", sample)
        self.assertIn("semanticCapability", sample)
