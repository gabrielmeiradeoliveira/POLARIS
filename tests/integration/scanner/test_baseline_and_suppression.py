from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_scanner.baseline import extract_suppression, filter_new_debt


class TestBaselineAndSuppression(unittest.TestCase):
    def test_inline_suppression_all_comment_styles(self) -> None:
        self.assertEqual(extract_suppression("x = 1  # polaris-ignore: PY-SEC-001 -- false positive"), ("PY-SEC-001", "false positive"))
        self.assertEqual(extract_suppression("eval(x); // polaris-ignore: FE-SEC-004 -- sandboxed"), ("FE-SEC-004", "sandboxed"))
        self.assertEqual(extract_suppression("/* polaris-ignore: CPP-SEC-001 -- bounded */"), ("CPP-SEC-001", "bounded"))
        self.assertEqual(extract_suppression("<!-- polaris-ignore: FE-SEC-007 -- trusted -->"), ("FE-SEC-007", "trusted"))

    def test_baseline_diff_gate_separates_new_debt(self) -> None:
        issues = [
            {"fingerprint": "fp-old", "severity": "CRITICAL"},
            {"fingerprint": "fp-new", "severity": "CRITICAL"},
        ]
        new_debt, legacy = filter_new_debt(issues, {"fp-old"})
        self.assertEqual([i["fingerprint"] for i in new_debt], ["fp-new"])
        self.assertEqual([i["fingerprint"] for i in legacy], ["fp-old"])


if __name__ == "__main__":
    unittest.main()
