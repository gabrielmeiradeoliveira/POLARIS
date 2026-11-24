import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class TestVerticalV1V3Scanner(unittest.TestCase):
    def test_nullability_and_resource_leak_through_scanner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"
            proj.mkdir()
            (proj / "null_vuln.py").write_text(
                "def f(flag):\n"
                "    u = None\n"
                "    if flag:\n"
                "        u = 'ok'\n"
                "    return u.upper()\n",
                encoding="utf-8",
            )
            (proj / "null_safe.py").write_text(
                "def f(flag):\n"
                "    u = None\n"
                "    if flag:\n"
                "        u = 'ok'\n"
                "    if u is not None:\n"
                "        return u.upper()\n"
                "    return ''\n",
                encoding="utf-8",
            )
            (proj / "res_leak.py").write_text(
                "def read_bad():\n"
                "    f = open('a.txt')\n"
                "    return f.read()\n",
                encoding="utf-8",
            )
            (proj / "res_safe.py").write_text(
                "def read_good():\n"
                "    with open('a.txt') as f:\n"
                "        return f.read()\n",
                encoding="utf-8",
            )

            out_json = Path(tmp) / "report.json"
            res = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "polaris_scanner.cli",
                    "analyze",
                    "--target",
                    str(proj),
                    "--project",
                    "v1-v3-test",
                    "--output",
                    str(out_json),
                ],
                cwd=str(ROOT),
                env={"PYTHONPATH": str(ROOT / "src")},
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            data = json.loads(out_json.read_text(encoding="utf-8"))
            issues = data.get("issues", [])

            null_files = {i["location"]["file"] for i in issues if i["ruleId"] == "PY-SEM-NULL-001"}
            res_files = {i["location"]["file"] for i in issues if i["ruleId"] == "PY-SEM-RES-001"}

            self.assertEqual(null_files, {"null_vuln.py"})
            self.assertEqual(res_files, {"res_leak.py"})


if __name__ == "__main__":
    unittest.main()
