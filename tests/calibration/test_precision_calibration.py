from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "python"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "sql"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "typescript"))

from taint_engine import analyze_python_taint
from polaris_sql_analyzer import analyze_sql_file
from polaris_ts_analyzer import analyze_ts_content


class TestPrecisionCalibration(unittest.TestCase):
    def test_real_python_calibration(self) -> None:
        vulns = [
            "import os\ndef v1():\n    x = input()\n    os.system(x)\n",
            "import subprocess\ndef v2():\n    c = input()\n    subprocess.run(c)\n",
            "def v3(cursor):\n    q = input()\n    cursor.execute(q)\n",
        ]
        cleans = [
            "import shlex, os\ndef c1():\n    q = shlex.quote(input())\n    os.system(q)\n",
            "def c2(a: int, b: int) -> int:\n    return a + b\n",
            "def c3(items: list[str]) -> list[str]:\n    return [i.strip() for i in items if i]\n",
            "import os\ndef c4(name: str) -> str:\n    return os.path.basename(name)\n",
            "def c5(val: str) -> int:\n    return int(val)\n",
        ]
        tp = sum(1 for v in vulns if analyze_python_taint(ast.parse(v), source_code=v))
        self.assertEqual(tp, 3)
        fp = sum(len(analyze_python_taint(ast.parse(c), source_code=c)) for c in cleans)
        self.assertEqual(fp, 0)

    def test_real_sql_calibration(self) -> None:
        vulns = [
            "SELECT * FROM users;",
            "DELETE FROM orders;",
            "UPDATE accounts SET balance = 0;",
        ]
        cleans = [
            "SELECT id, name FROM users WHERE id = 1;",
            "DELETE FROM orders WHERE id = 42;",
            "UPDATE accounts SET balance = 100 WHERE id = 1;",
            "INSERT INTO logs (msg) VALUES ('ok');",
            "CREATE TABLE items (id INT PRIMARY KEY, name VARCHAR(50));",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tp = 0
            for idx, sql in enumerate(vulns):
                p = root / f"v{idx}.sql"
                p.write_text(sql, encoding="utf-8")
                issues, _ = analyze_sql_file(p, root)
                if issues:
                    tp += 1
            fp = 0
            for idx, sql in enumerate(cleans):
                p = root / f"c{idx}.sql"
                p.write_text(sql, encoding="utf-8")
                issues, _ = analyze_sql_file(p, root)
                fp += len(issues)
        self.assertEqual(tp, 3)
        self.assertEqual(fp, 0)

    def test_real_typescript_calibration(self) -> None:
        vulns = [
            "export const A = ({ html }: { html: string }) => <div dangerouslySetInnerHTML={{ __html: html }} />;",
            "export function run(code: string) { return eval(code); }",
            "export const Link = () => <a href=\"javascript:alert(1)\">click</a>;",
        ]
        cleans = [
            "export const Safe = ({ text }: { text: string }) => <div>{text}</div>;",
            "export function add(a: number, b: number): number { return a + b; }",
            "export const Nav = () => <a href=\"/dashboard\">Dashboard</a>;",
            "export function setSafe(el: HTMLElement) { el.textContent = 'ok'; }",
            "export const items = [1, 2, 3].map((x) => x * 2);",
        ]
        tp = sum(1 for v in vulns if analyze_ts_content(v))
        fp = sum(len(analyze_ts_content(c)) for c in cleans)
        self.assertEqual(tp, 3)
        self.assertEqual(fp, 0)


if __name__ == "__main__":
    unittest.main()
