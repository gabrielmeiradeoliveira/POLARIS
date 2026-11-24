import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from polaris_scanner.contracts import validate_analysis_result


class TestCrossRuntimeContract(unittest.TestCase):
    def test_schema_file_matches_contract_version(self) -> None:
        schema_path = Path(__file__).resolve().parents[2] / "contracts" / "analysis-result.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], "1.0.0")

    def test_cross_runtime_sample_payloads_valid(self) -> None:
        for lang, analyzer_id, file_path in (
            ("python", "polaris-python-analyzer", "src/main.py"),
            ("csharp", "polaris-csharp-analyzer", "src/Program.cs"),
            ("java", "polaris-java-analyzer", "src/Main.java"),
            ("sql", "polaris-sql-analyzer", "sql/query.sql"),
        ):
            payload = {
                "schemaVersion": "1.0.0",
                "analysisId": f"id-{lang}",
                "projectKey": "cross-runtime",
                "branch": "main",
                "analyzer": {"id": analyzer_id, "version": "2.0.0"},
                "status": "COMPLETED",
                "totalFiles": 1,
                "diagnostics": [],
                "issues": [
                    {
                        "ruleId": f"{lang.upper()}-001",
                        "language": lang,
                        "severity": "MINOR",
                        "location": {"file": file_path, "startLine": 1},
                        "message": "Cross-runtime check",
                    }
                ],
            }
            self.assertEqual(validate_analysis_result(payload), [])


if __name__ == "__main__":
    unittest.main()
