import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from polaris_server.issues_service import _csv_safe_cell  # noqa: E402


class TestOnda1Onda4(unittest.TestCase):
    def test_csv_formula_injection_protection(self):
        self.assertEqual(_csv_safe_cell("=CMD()"), '"\'=CMD()"')
        self.assertEqual(_csv_safe_cell("+1+1"), '"\'+1+1"')
        self.assertEqual(_csv_safe_cell("-1"), '"\'-1"')
        self.assertEqual(_csv_safe_cell("@SUM(A1)"), '"\'@SUM(A1)"')
        self.assertEqual(_csv_safe_cell('safe "text"'), '"safe ""text"""')
