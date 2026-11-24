from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "legacy"))

from polaris_scanner.safe_reader import classify_file_scope, read_text_safe
from polaris_legacy_analyzer import analyze_legacy_content


class TestLegacyResilience(unittest.TestCase):
    def test_cp1252_and_latin1_never_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "legacy_cp1252.py"
            p.write_bytes("print 'Olá mundo'\n".encode("cp1252"))
            text, err = read_text_safe(p)
            self.assertIsNone(err)
            self.assertIn("Ol", text)

    def test_scope_classification(self) -> None:
        self.assertEqual(classify_file_scope("tests/unit/test_a.py"), "test")
        self.assertEqual(classify_file_scope("src/migrations/001.sql"), "generated")
        self.assertEqual(classify_file_scope("src/app.py"), "prod")

    def test_legacy_all_6_rules(self) -> None:
        code = "\n".join([
            "h = MD5(x)",
            "proto = SecurityProtocolType.Tls",
            "obj = pickle.loads(data)",
            "doc = XmlDocument()",
            'connectionString = "Server=db;Password=Secret123;"',
            "conn = SqlConnection(cs)",
        ])
        ids = {i["ruleId"].split(":")[1] for i in analyze_legacy_content(code)}
        self.assertEqual(ids, {"LEG-SEC-001", "LEG-SEC-002", "LEG-SEC-003", "LEG-SEC-004", "LEG-SEC-005", "LEG-REL-001"})


if __name__ == "__main__":
    unittest.main()
