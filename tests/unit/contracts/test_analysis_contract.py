import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_scanner.contracts import validate_analysis_result, write_report_atomic


class TestAnalysisContract(unittest.TestCase):
    def test_valid_contract_payload(self) -> None:
        payload = {
            "schemaVersion": "1.0.0",
            "analysisId": "abc-123",
            "projectKey": "demo",
            "branch": "main",
            "analyzer": {"id": "polaris-python-analyzer", "version": "2.0.0"},
            "status": "COMPLETED",
            "totalFiles": 1,
            "diagnostics": [],
            "issues": [
                {
                    "ruleId": "PY-001",
                    "language": "python",
                    "severity": "MAJOR",
                    "location": {"file": "src/app.py", "startLine": 1, "startColumn": 1},
                    "message": "Example issue",
                }
            ],
        }
        self.assertEqual(validate_analysis_result(payload), [])

    def test_invalid_location_and_status_rejected(self) -> None:
        payload = {
            "schemaVersion": "1.0.0",
            "analysisId": "abc-123",
            "projectKey": "demo",
            "branch": "main",
            "analyzer": {"id": "polaris-python-analyzer", "version": "2.0.0"},
            "status": "UNKNOWN_STATE",
            "totalFiles": 1,
            "diagnostics": [],
            "issues": [
                {
                    "ruleId": "PY-001",
                    "language": "python",
                    "severity": "MAJOR",
                    "location": {"file": "../escape.py", "startLine": 0},
                    "message": "Bad location",
                }
            ],
        }
        errors = validate_analysis_result(payload)
        self.assertGreaterEqual(len(errors), 3)

    def test_atomic_utf8_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "report.json"
            write_report_atomic({"ok": True, "text": "ação"}, out)
            loaded = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(loaded["text"], "ação")


if __name__ == "__main__":
    unittest.main()
