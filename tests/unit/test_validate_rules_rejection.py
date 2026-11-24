import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validation" / "validate_rules.py"


class TestValidateRulesRejection(unittest.TestCase):
    def test_10_rejection_scenarios(self) -> None:
        scenarios = [
            ("01_missing_fixtures_dir", ["--language", "python", "--fixtures-dir", "Z:/nonexistent_dir_123"]),
            ("02_empty_fixtures_dir", ["--language", "python", "--fixtures-dir", "__TMP__"]),
            ("03_nonexistent_rule", ["--rule", "NO-SUCH-RULE-999"]),
            ("04_missing_code_field", ["--rule", "PY-SYN-001", "--fixtures-dir", "__TMP_NO_CODE__"]),
            ("05_empty_cases_list", ["--rule", "PY-SYN-001", "--fixtures-dir", "__TMP_EMPTY_CASES__"]),
            ("06_invalid_json_fixture", ["--rule", "PY-SYN-001", "--fixtures-dir", "__TMP_BAD_JSON__"]),
            ("07_divergent_expected_positive", ["--rule", "PY-SYN-001", "--fixtures-dir", "__TMP_DIVERGENT__"]),
            ("08_all_rules_incomplete", ["--all"]),
            ("09_csharp_missing_cases", ["--rule", "CS-SYN-001", "--fixtures-dir", "__TMP__"]),
            ("10_java_missing_cases", ["--rule", "JV-SYN-001", "--fixtures-dir", "__TMP__"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "no_code" / "python").mkdir(parents=True)
            (tmp_path / "no_code" / "python" / "PY-SYN-001.json").write_text(
                '{"ruleId":"PY-SYN-001","cases":[{"caseId":"1","expectedPositive":true}]}', encoding="utf-8"
            )
            (tmp_path / "empty_cases" / "python").mkdir(parents=True)
            (tmp_path / "empty_cases" / "python" / "PY-SYN-001.json").write_text(
                '{"ruleId":"PY-SYN-001","cases":[]}', encoding="utf-8"
            )
            (tmp_path / "bad_json" / "python").mkdir(parents=True)
            (tmp_path / "bad_json" / "python" / "PY-SYN-001.json").write_text("{bad json", encoding="utf-8")
            (tmp_path / "divergent" / "python").mkdir(parents=True)
            (tmp_path / "divergent" / "python" / "PY-SYN-001.json").write_text(
                '{"ruleId":"PY-SYN-001","cases":[{"caseId":"1","expectedPositive":true,"code":"x = 1"}]}', encoding="utf-8"
            )

            for name, args in scenarios:
                with self.subTest(scenario=name):
                    resolved = [
                        str(tmp_path) if a == "__TMP__"
                        else str(tmp_path / "no_code") if a == "__TMP_NO_CODE__"
                        else str(tmp_path / "empty_cases") if a == "__TMP_EMPTY_CASES__"
                        else str(tmp_path / "bad_json") if a == "__TMP_BAD_JSON__"
                        else str(tmp_path / "divergent") if a == "__TMP_DIVERGENT__"
                        else a
                        for a in args
                    ]
                    proc = subprocess.run([sys.executable, str(VALIDATOR), *resolved], capture_output=True, text=True)
                    self.assertNotEqual(proc.returncode, 0, f"Scenario {name} should have been rejected")


if __name__ == "__main__":
    unittest.main()
