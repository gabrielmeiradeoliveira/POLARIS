from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_server.triage import IssueRecord, compute_persistent_fingerprint


class TestIssueFingerprintTriage(unittest.TestCase):
    def test_persistent_fingerprint_and_triage_audit(self) -> None:
        fp1 = compute_persistent_fingerprint("proj-1", "python:PY-SEC-001", "app.py", "  cursor.execute(q)  ")
        fp2 = compute_persistent_fingerprint("proj-1", "python:PY-SEC-001", "app.py", "cursor.execute(q)")
        self.assertEqual(fp1, fp2)
        rec = IssueRecord(fingerprint=fp1, rule_id="python:PY-SEC-001", file_path="app.py", line=10)
        rec.triage("FALSE_POSITIVE", "Sanitized upstream", "gabriel")
        self.assertEqual(rec.status, "FALSE_POSITIVE")
        self.assertEqual(len(rec.audit_log), 1)
        with self.assertRaises(ValueError):
            rec.triage("OPEN", "   ", "gabriel")


if __name__ == "__main__":
    unittest.main()
