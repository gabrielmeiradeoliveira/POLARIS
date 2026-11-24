from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_scanner.contracts import validate_analysis_result


class TestGoPythonContractParity(unittest.TestCase):
    def test_go_contract_matches_adr_010_v1(self) -> None:
        # Mirrors AnalysisReportV1 produced by scanner-go/internal/contract/contract.go
        go_sample = {
            "schemaVersion": "1.0.0",
            "analysisId": "go-scan-1",
            "projectKey": "polaris-self",
            "branch": "main",
            "analyzer": {"id": "polaris-scanner-go", "version": "2.7.0"},
            "status": "COMPLETED",
            "totalFiles": 12,
            "diagnostics": [],
            "issues": [
                {
                    "ruleId": "go:GO-SEC-001",
                    "language": "python",
                    "severity": "CRITICAL",
                    "confidence": "HIGH",
                    "location": {"file": "app.py", "startLine": 1},
                    "message": "Parity check",
                }
            ],
        }
        self.assertEqual(validate_analysis_result(go_sample), [])


if __name__ == "__main__":
    unittest.main()
