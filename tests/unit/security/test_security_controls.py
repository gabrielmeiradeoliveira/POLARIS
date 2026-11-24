import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "analyzers" / "python"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "validation"))

from polaris_python_analyzer import analyze_python_file
from polaris_scanner.contracts import is_valid_relative_posix_path
from scan_secrets import scan_text


class TestSecurityControls(unittest.TestCase):
    def test_analyzed_python_code_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "pwned.txt"
            target = root / "evil.py"
            target.write_text(f"open(r'{marker}', 'w').write('executed')\neval('1+1')\n", encoding="utf-8")
            issues, _ = analyze_python_file(target, root)
            self.assertFalse(marker.exists())
            self.assertTrue(any(i["ruleId"] == "PY-SYN-001" for i in issues))

    def test_path_traversal_rejected(self) -> None:
        self.assertFalse(is_valid_relative_posix_path("../secret.py"))
        self.assertFalse(is_valid_relative_posix_path("/etc/passwd"))
        self.assertFalse(is_valid_relative_posix_path("a\\b.py"))
        self.assertTrue(is_valid_relative_posix_path("src/app.py"))

    def test_secret_scanner_detects_synthetic_secret(self) -> None:
        synthetic_key = "AKIA" + "1234567890ABCDEF"
        self.assertEqual(scan_text(synthetic_key), ["aws_access_key"])
        self.assertEqual(scan_text("normal_code = 1"), [])


if __name__ == "__main__":
    unittest.main()
