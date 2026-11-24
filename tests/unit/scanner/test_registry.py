import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_scanner.registry import AnalyzerRegistry


class TestAnalyzerRegistry(unittest.TestCase):
    def test_default_registry_has_four_languages(self) -> None:
        reg = AnalyzerRegistry()
        for lang in ("python", "csharp", "java", "sql"):
            spec = reg.get_by_language(lang)
            self.assertIsNotNone(spec)
            self.assertEqual(spec.contract_version, "1.0.0")
            self.assertTrue(len(spec.command) >= 2)
            self.assertTrue(len(spec.capabilities) >= 1)


if __name__ == "__main__":
    unittest.main()
