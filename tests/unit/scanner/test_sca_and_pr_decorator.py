from __future__ import annotations

import unittest

from polaris_scanner.sca import parse_package_json, parse_requirements_txt, scan_dependencies_offline
from polaris_server.pr_decorator import POLARIS_MARKER, PrSummary, render_pr_summary_markdown


class TestScaAndPrDecorator(unittest.TestCase):
    def test_sca_offline_detection(self) -> None:
        deps = parse_requirements_txt("requirements.txt", "urllib3==1.26.4\n")
        deps += parse_package_json("package.json", '{"dependencies": {"lodash": "4.17.20"}}')
        db = {
            "PyPI:urllib3": [{"id": "CVE-2021-33503", "cvss": 7.5, "affected_versions": ["1.26.4"], "fixed_version": "1.26.5"}],
            "npm:lodash": [{"id": "CVE-2021-23337", "cvss": 9.1, "affected_versions": ["4.17.20"], "fixed_version": "4.17.21"}],
        }
        findings = scan_dependencies_offline(deps, db)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].severity, "CRITICAL")
        self.assertEqual(findings[1].severity, "BLOCKER")

    def test_pr_decorator_markdown_idempotent_marker(self) -> None:
        md = render_pr_summary_markdown(PrSummary("proj", "PR-42", "PASSED", 0, 0, 1, 92.5, 0.0))
        self.assertIn(POLARIS_MARKER, md)
        self.assertIn("PASSED", md)


if __name__ == "__main__":
    unittest.main()
