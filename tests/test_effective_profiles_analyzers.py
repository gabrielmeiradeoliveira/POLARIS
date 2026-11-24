import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analyzers" / "python"))
sys.path.insert(0, str(ROOT / "analyzers" / "sql"))

import polaris_python_analyzer as py_analyzer  # noqa: E402
import polaris_sql_analyzer as sql_analyzer  # noqa: E402


class TestEffectiveProfilesAnalyzers(unittest.TestCase):
    def test_python_disabled_rule_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "sample.py"
            f.write_text("def run(x):\n    return eval(x)\n", encoding="utf-8")

            os.environ.pop("POLARIS_DISABLED_RULES", None)
            issues_on, _ = py_analyzer.analyze_python_file(f, Path(tmp))
            self.assertTrue(any(i["ruleId"] == "PY-SYN-001" for i in issues_on))

            os.environ["POLARIS_DISABLED_RULES"] = "PY-SYN-001"
            try:
                issues_off, _ = py_analyzer.analyze_python_file(f, Path(tmp))
                self.assertFalse(any(i["ruleId"] == "PY-SYN-001" for i in issues_off))
            finally:
                os.environ.pop("POLARIS_DISABLED_RULES", None)

    def test_python_future_import_not_flagged_unused(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "future_mod.py"
            f.write_text("from __future__ import annotations\n\ndef ok() -> int:\n    return 1\n", encoding="utf-8")
            os.environ.pop("POLARIS_DISABLED_RULES", None)
            issues, _ = py_analyzer.analyze_python_file(f, Path(tmp))
            self.assertFalse(any(i["ruleId"] == "PY-REL-015" for i in issues))

    def test_python_nullness_urlparse_and_real_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "null_mod.py"
            f.write_text(
                "from urllib.parse import urlparse\n"
                "def safe_parse(u: str):\n"
                "    p = urlparse(u)\n"
                "    return p.scheme\n"
                "def unsafe_none():\n"
                "    x = None\n"
                "    return x.strip()\n",
                encoding="utf-8",
            )
            os.environ.pop("POLARIS_DISABLED_RULES", None)
            issues, _ = py_analyzer.analyze_python_file(f, Path(tmp))
            null_issues = [i for i in issues if i["ruleId"] == "PY-SEM-NULL-001"]
            self.assertTrue(any("x.strip" in i["message"] for i in null_issues))
            self.assertFalse(any("p.scheme" in i["message"] for i in null_issues))

    def test_cobertura_xml_legit_and_malicious(self):
        sys.path.insert(0, str(ROOT / "src"))
        from polaris_server.coverage_duplication import parse_cobertura_xml

        ok = parse_cobertura_xml('<coverage><packages><package><classes><class filename="a.py"><lines><line number="1" hits="1"/></lines></class></classes></package></packages></coverage>', {"a.py"})
        self.assertEqual(ok["lines_valid"], 1)
        with self.assertRaises(ValueError):
            parse_cobertura_xml('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><coverage/>', set())

    def test_sql_disabled_rule_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "query.sql"
            f.write_text("SELECT * FROM users;\n", encoding="utf-8")

            os.environ.pop("POLARIS_DISABLED_RULES", None)
            issues_on, _ = sql_analyzer.analyze_sql_file(f, Path(tmp))
            self.assertTrue(any(i["ruleId"] == "SQL-SYN-001" for i in issues_on))

            os.environ["POLARIS_DISABLED_RULES"] = "SQL-SYN-001"
            try:
                issues_off, _ = sql_analyzer.analyze_sql_file(f, Path(tmp))
                self.assertFalse(any(i["ruleId"] == "SQL-SYN-001" for i in issues_off))
            finally:
                os.environ.pop("POLARIS_DISABLED_RULES", None)

    def test_python_future_import_not_flagged_unused(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "future_mod.py"
            f.write_text("from __future__ import annotations\n\ndef ok() -> int:\n    return 1\n", encoding="utf-8")
            os.environ.pop("POLARIS_DISABLED_RULES", None)
            issues, _ = py_analyzer.analyze_python_file(f, Path(tmp))
            self.assertFalse(any(i["ruleId"] == "PY-REL-015" for i in issues))

    def test_python_nullness_urlparse_and_real_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "null_mod.py"
            f.write_text(
                "from urllib.parse import urlparse\n"
                "def safe_parse(u: str):\n"
                "    p = urlparse(u)\n"
                "    return p.scheme\n"
                "def unsafe_none():\n"
                "    x = None\n"
                "    return x.strip()\n",
                encoding="utf-8",
            )
            os.environ.pop("POLARIS_DISABLED_RULES", None)
            issues, _ = py_analyzer.analyze_python_file(f, Path(tmp))
            null_issues = [i for i in issues if i["ruleId"] == "PY-SEM-NULL-001"]
            self.assertTrue(any("x.strip" in i["message"] for i in null_issues))
            self.assertFalse(any("p.scheme" in i["message"] for i in null_issues))

    def test_cobertura_xml_legit_and_malicious(self):
        sys.path.insert(0, str(ROOT / "src"))
        from polaris_server.coverage_duplication import parse_cobertura_xml

        ok = parse_cobertura_xml('<coverage><packages><package><classes><class filename="a.py"><lines><line number="1" hits="1"/></lines></class></classes></package></packages></coverage>', {"a.py"})
        self.assertEqual(ok["lines_valid"], 1)
        with self.assertRaises(ValueError):
            parse_cobertura_xml('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><coverage/>', set())
