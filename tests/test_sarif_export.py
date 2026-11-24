import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from polaris_server.issues_service import build_sarif_report  # noqa: E402


class TestSarifExport(unittest.TestCase):
    def test_sarif_2_1_0_structure(self):
        sarif = build_sarif_report(
            [
                {
                    "rule_id": "PY-SYN-001",
                    "severity": "CRITICAL",
                    "message": "Avoid eval",
                    "file_path": "app.py",
                    "start_line": 2,
                }
            ]
        )
        self.assertEqual(sarif["version"], "2.1.0")
        self.assertEqual(len(sarif["runs"]), 1)
        res = sarif["runs"][0]["results"][0]
        self.assertEqual(res["ruleId"], "PY-SYN-001")
        self.assertEqual(res["level"], "error")
        self.assertEqual(res["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "app.py")
