import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_scanner.discovery import discover_files


class TestScannerDiscovery(unittest.TestCase):
    def test_deterministic_four_languages_unicode_and_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b_dir").mkdir()
            (root / "a dir with spaces").mkdir()
            (root / ".git").mkdir()
            (root / "custom_skip").mkdir()

            (root / "b_dir" / "Main.java").write_text("class Main {}", encoding="utf-8")
            (root / "a dir with spaces" / "ação_unicode.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "Program.cs").write_text("class Program {}", encoding="utf-8")
            (root / "query.sql").write_text("SELECT 1;", encoding="utf-8")
            (root / ".git" / "ignored.py").write_text("x = 1", encoding="utf-8")
            (root / "custom_skip" / "ignored.sql").write_text("SELECT 2;", encoding="utf-8")

            res = discover_files(root, exclusions=(".git", "custom_skip"))
            rel_paths = [f.relative_path for f in res.files]
            self.assertEqual(
                rel_paths,
                [
                    "Program.cs",
                    "a dir with spaces/ação_unicode.py",
                    "b_dir/Main.java",
                    "query.sql",
                ],
            )
            self.assertEqual([f.language for f in res.files], ["csharp", "python", "java", "sql"])

    def test_limits_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "small.py").write_text("x=1", encoding="utf-8")
            (root / "big.py").write_text("x" * 100, encoding="utf-8")
            res = discover_files(root, max_file_bytes=20)
            self.assertEqual([f.relative_path for f in res.files], ["small.py"])
            self.assertEqual(len(res.skipped), 1)
            self.assertEqual(res.skipped[0].reason, "exceeds_max_file_bytes")


if __name__ == "__main__":
    unittest.main()
