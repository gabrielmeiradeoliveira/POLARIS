import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analyzers" / "python"))

from project_index import ProjectIndex  # noqa: E402


class TestIncrementalEquivalence(unittest.TestCase):
    def _run_scanner(self, proj: Path, out_json: Path) -> list[dict]:
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "polaris_scanner.cli",
                "analyze",
                "--target",
                str(proj),
                "--project",
                "inc-eq-test",
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
        return json.loads(out_json.read_text(encoding="utf-8")).get("issues", [])

    def test_transitive_invalidation_and_equivalence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"
            proj.mkdir()
            (proj / "helper.py").write_text(
                "def read_data():\n"
                "    f = open('x.txt')\n"
                "    return f.read()\n",
                encoding="utf-8",
            )
            (proj / "app.py").write_text(
                "import helper\n"
                "def main():\n"
                "    return helper.read_data()\n",
                encoding="utf-8",
            )

            idx = ProjectIndex(proj)
            idx.index_directory()
            k1 = idx.compute_cache_key("app.py")

            issues_1 = self._run_scanner(proj, Path(tmp) / "r1.json")
            self.assertTrue(any(i["ruleId"] == "PY-SEM-RES-001" for i in issues_1))

            # Fix helper.py (vulnerable -> safe)
            (proj / "helper.py").write_text(
                "def read_data():\n"
                "    with open('x.txt') as f:\n"
                "        return f.read()\n",
                encoding="utf-8",
            )
            idx.index_file(proj / "helper.py")
            k2 = idx.compute_cache_key("app.py")
            self.assertNotEqual(k1, k2)

            issues_2 = self._run_scanner(proj, Path(tmp) / "r2.json")
            self.assertFalse(any(i["ruleId"] == "PY-SEM-RES-001" for i in issues_2))


if __name__ == "__main__":
    unittest.main()
