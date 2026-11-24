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


class TestPythonTaintE2E(unittest.TestCase):
    def test_multifile_sqli_cmdi_path_and_safe(self) -> None:
        vuln_files = {
            "controller.py": "def get_user(uid):\n    return find_user(uid)\n",
            "service.py": "def find_user(uid):\n    return query_user(uid)\n",
            "repo.py": "def query_user(uid):\n    cursor.execute('SELECT * FROM users WHERE id=' + uid)\n",
        }
        issues = run_py_analyzer(vuln_files)
        sqli = [i for i in issues if i.get("cwe") == "CWE-89"]
        self.assertTrue(len(sqli) >= 1, f"Expected CWE-89, got {issues}")
        self.assertTrue(len(sqli[0].get("flowSteps", [])) >= 3)

        safe_files = {
            "controller.py": "def get_user(uid):\n    return query_user(uid)\n",
            "repo.py": "def query_user(uid):\n    cursor.execute('SELECT * FROM users WHERE id=%s', (uid,))\n",
        }
        safe_issues = run_py_analyzer(safe_files)
        self.assertEqual([i for i in safe_issues if i.get("cwe") == "CWE-89"], [])

        cmd_files = {
            "routes.py": "def run_cmd(arg):\n    return subprocess.run('ls ' + arg)\n",
        }
        cmd_issues = run_py_analyzer(cmd_files)
        self.assertTrue(any(i.get("cwe") == "CWE-78" for i in cmd_issues))

        path_files = {
            "views.py": "def read_file(name):\n    return open('/var/data/' + name).read()\n",
        }
        path_issues = run_py_analyzer(path_files)
        self.assertTrue(any(i.get("cwe") == "CWE-22" for i in path_issues))


if __name__ == "__main__":
    unittest.main()
