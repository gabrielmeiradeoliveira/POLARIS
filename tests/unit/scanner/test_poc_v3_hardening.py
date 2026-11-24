from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from poc.field_trial import run_field_trial


class TestPocV3Hardening(unittest.TestCase):
    def test_hostile_corpus_zero_file_errors_and_skips_binaries_minified(self) -> None:
        poc_dir = REPO_ROOT / "poc"
        res = run_field_trial(poc_dir / "POST_HARDENING_REPORT.md", poc_dir / "baseline_audit.json")
        self.assertEqual(res["file_errors"], 0)
        self.assertEqual(res["files_skipped"], 2)
        self.assertGreaterEqual(res["total_issues"], 8)


if __name__ == "__main__":
    unittest.main()
