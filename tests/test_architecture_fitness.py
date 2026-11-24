from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestArchitectureFitness(unittest.TestCase):
    def test_scanner_does_not_import_server(self) -> None:
        scanner_dir = ROOT / "src" / "polaris_scanner"
        for py in scanner_dir.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertFalse(alias.name.startswith("polaris_server"), f"{py}: forbidden import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self.assertFalse(node.module.startswith("polaris_server"), f"{py}: forbidden import {node.module}")

    def test_pilot_fixtures_have_real_code(self) -> None:
        pilot_dir = ROOT / "tests" / "fixtures" / "pilot_160"
        fixtures = list(pilot_dir.rglob("*.json"))
        self.assertGreaterEqual(len(fixtures), 20)
        for f in fixtures:
            data = json.loads(f.read_text(encoding="utf-8"))
            cases = data.get("cases", [])
            self.assertGreaterEqual(len(cases), 8, f"{f} has <8 cases")
            for c in cases:
                self.assertIn("code", c, f"{f} missing 'code'")

    def test_analyzer_binaries_present(self) -> None:
        self.assertTrue((ROOT / "analyzers" / "csharp" / "bin" / "Release" / "net10.0" / "PolarisCSharpAnalyzer.dll").exists())
        self.assertTrue((ROOT / "analyzers" / "java" / "target" / "polaris-java-analyzer.jar").exists())


if __name__ == "__main__":
    unittest.main()
