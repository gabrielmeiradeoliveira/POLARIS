import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATE_SCRIPT = REPO_ROOT / "scripts" / "validation" / "validate_rules.py"


class TestValidateRulesUnification(unittest.TestCase):
    def test_all_includes_pilot_cases(self):
        proc = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), "--all"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        import re
        m_cases = re.search(r"CASES_EXECUTED=(\d+)", proc.stdout)
        m_passed = re.search(r"RULES_PASSED=(\d+)", proc.stdout)
        self.assertIsNotNone(m_cases, proc.stdout)
        self.assertIsNotNone(m_passed, proc.stdout)
        self.assertGreaterEqual(int(m_cases.group(1)), 160)
        self.assertGreaterEqual(int(m_passed.group(1)), 20)


if __name__ == "__main__":
    unittest.main()
