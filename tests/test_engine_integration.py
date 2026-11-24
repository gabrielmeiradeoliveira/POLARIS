from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CS_DLL = ROOT / "analyzers" / "csharp" / "bin" / "Release" / "net10.0" / "PolarisCSharpAnalyzer.dll"
JV_JAR = ROOT / "analyzers" / "java" / "target" / "polaris-java-analyzer.jar"


class TestEngineIntegration(unittest.TestCase):
    def test_csharp_non_pilot_rule_executed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tpath = Path(td)
            f = tpath / "Test.cs"
            f.write_text("using System;\nclass C { void M() { try { } catch (Exception ex) { throw ex; } } }\n", encoding="utf-8")
            proc = subprocess.run(["dotnet", str(CS_DLL), "--root", str(tpath), str(f)], capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            rule_ids = {i.get("ruleId") for i in payload.get("issues", [])}
            self.assertIn("CS-REL-002", rule_ids)

    def test_java_non_pilot_rule_executed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tpath = Path(td)
            f = tpath / "Test.java"
            f.write_text("class C { void m() { try { } catch (Throwable t) { } } }\n", encoding="utf-8")
            proc = subprocess.run(["java", "-jar", str(JV_JAR), "--root", str(tpath), str(f)], capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            rule_ids = {i.get("ruleId") for i in payload.get("issues", [])}
            self.assertIn("JV-REL-002", rule_ids)


if __name__ == "__main__":
    unittest.main()
