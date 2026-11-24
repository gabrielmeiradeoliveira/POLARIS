import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY_ANALYZER = ROOT / "analyzers" / "python" / "polaris_python_analyzer.py"


def run_py_analyzer(files: dict[str, str]) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        paths = []
        for rel, content in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            paths.append(str(p))
        proc = subprocess.run(
            [sys.executable, str(PY_ANALYZER), "--root", str(tmp_path), *paths],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)["issues"]


class TestPython90Scenarios(unittest.TestCase):
    def test_90_python_scenarios(self) -> None:
        scenarios = []
        for i in range(15):
            scenarios.append((
                f"sqli_pos_{i}",
                {
                    "controller.py": f"def handle_{i}(uid):\n    return find_{i}(uid)\n",
                    "service.py": f"def find_{i}(uid):\n    return query_{i}(uid)\n",
                    "repo.py": f"def query_{i}(uid):\n    cursor.execute('SELECT * FROM users WHERE id=' + uid)\n",
                },
                "CWE-89",
                True,
            ))
            scenarios.append((
                f"sqli_neg_{i}",
                {
                    "controller.py": f"def handle_{i}(uid):\n    return query_{i}(uid)\n",
                    "repo.py": f"def query_{i}(uid):\n    cursor.execute('SELECT * FROM users WHERE id=%s', (uid,))\n",
                },
                "CWE-89",
                False,
            ))
        for i in range(15):
            scenarios.append((
                f"cmdi_pos_{i}",
                {"routes.py": f"import subprocess\ndef run_{i}(arg):\n    return subprocess.run('ls ' + arg)\n"},
                "CWE-78",
                True,
            ))
            scenarios.append((
                f"cmdi_neg_{i}",
                {"routes.py": f"def run_{i}(arg):\n    return arg.strip()\n"},
                "CWE-78",
                False,
            ))
        for i in range(15):
            scenarios.append((
                f"path_pos_{i}",
                {"views.py": f"def read_{i}(name):\n    return open('/var/data/' + name).read()\n"},
                "CWE-22",
                True,
            ))
            scenarios.append((
                f"path_neg_{i}",
                {"views.py": f"def read_{i}(name):\n    return 'fixed.txt'\n"},
                "CWE-22",
                False,
            ))

        self.assertEqual(len(scenarios), 90)
        for name, files, expected_cwe, expected_hit in scenarios:
            with self.subTest(scenario=name):
                issues = run_py_analyzer(files)
                hits = [it for it in issues if it.get("cwe") == expected_cwe]
                if expected_hit:
                    self.assertTrue(len(hits) >= 1, f"Expected {expected_cwe} in {name}")
                else:
                    self.assertEqual(len(hits), 0, f"Unexpected {expected_cwe} in {name}: {hits}")


if __name__ == "__main__":
    unittest.main()
