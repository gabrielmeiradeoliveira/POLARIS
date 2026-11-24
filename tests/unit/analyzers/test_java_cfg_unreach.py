import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
JAVA_JAR = REPO_ROOT / "analyzers" / "java" / "target" / "polaris-java-analyzer.jar"


class TestJavaCfgUnreach(unittest.TestCase):
    def test_jv_sem_unreach_001_detects_unreachable_statement(self):
        if not JAVA_JAR.exists():
            self.skipTest(f"Java JAR not found at {JAVA_JAR}")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "UnreachSample.java"
            src.write_text(
                "public class UnreachSample {\n"
                "    public int foo(int x) {\n"
                "        if (x > 0) {\n"
                "            return 1;\n"
                "        }\n"
                "        return 0;\n"
                "        int dead = 42;\n"
                "    }\n"
                "}\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                ["java", "-jar", str(JAVA_JAR), str(src)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            rules = [i.get("ruleId") for i in payload.get("issues", [])]
            self.assertIn("JV-SEM-UNREACH-001", rules)


if __name__ == "__main__":
    unittest.main()
