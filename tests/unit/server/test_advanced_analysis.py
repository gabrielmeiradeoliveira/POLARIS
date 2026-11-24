from __future__ import annotations

import unittest

from polaris_server.coverage_duplication import detect_duplications, parse_cobertura_xml
from polaris_server.git_branch_service import list_branches, list_pull_requests, register_branch, register_pull_request


class TestAdvancedAnalysis(unittest.TestCase):
    def test_cobertura_xml_safe_parsing(self) -> None:
        xml = """<coverage><packages><package><classes>
        <class filename="src/app.py"><lines><line number="1" hits="1"/><line number="2" hits="0"/></lines></class>
        <class filename="../secret.py"><lines><line number="1" hits="1"/></lines></class>
        </classes></package></packages></coverage>"""
        res = parse_cobertura_xml(xml, {"src/app.py"})
        self.assertEqual(res["lines_valid"], 2)
        self.assertEqual(res["lines_covered"], 1)
        self.assertEqual(res["coverage_percent"], 50.0)

        with self.assertRaises(ValueError):
            parse_cobertura_xml("<!DOCTYPE foo><coverage/>", set())

    def test_duplication_detection(self) -> None:
        files = {
            "a.py": "def calc(x): return x * 2 + 1",
            "b.py": "def calc(x): return x * 2 + 1",
        }
        dup = detect_duplications(files, window_size=5)
        self.assertGreaterEqual(dup["duplicated_blocks_count"], 1)

    def test_branches_and_pull_requests_isolation(self) -> None:
        register_branch("proj-x", "main", is_main=True, last_commit="abc123", quality_gate_status="PASSED")
        register_branch("proj-x", "feat/login", is_main=False, last_commit="def456", quality_gate_status="FAILED", new_code_issues=2)
        register_pull_request("proj-x", "42", "feat/login", "main", "def456", quality_gate_status="FAILED", new_issues=[{"rule_id": "PY001"}])

        self.assertEqual(list_branches("proj-x")["total"], 2)
        self.assertEqual(list_pull_requests("proj-x")["total"], 1)


if __name__ == "__main__":
    unittest.main()
