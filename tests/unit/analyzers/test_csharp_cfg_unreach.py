import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DLL = ROOT / "analyzers" / "csharp" / "bin" / "Release" / "net10.0" / "PolarisCSharpAnalyzer.dll"


class TestCSharpCfgUnreachable(unittest.TestCase):
    def test_roslyn_cfg_unreachable_code_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cs_file = Path(tmp) / "Sample.cs"
            cs_file.write_text(
                "public class Sample {\n"
                "    public int Compute() {\n"
                "        return 42;\n"
                "        int dead = 1;\n"
                "    }\n"
                "}\n",
                encoding="utf-8",
            )
            res = subprocess.run(
                ["dotnet", str(DLL), str(cs_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            data = json.loads(res.stdout)
            unreach = [i for i in data.get("issues", []) if i["ruleId"] == "CS-SEM-UNREACH-001"]
            self.assertGreaterEqual(len(unreach), 1)
            self.assertEqual(unreach[0]["location"]["startLine"], 4)


if __name__ == "__main__":
    unittest.main()
