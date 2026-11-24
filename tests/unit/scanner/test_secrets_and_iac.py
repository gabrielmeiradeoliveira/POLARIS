from __future__ import annotations

import unittest

from polaris_analyzers.iac.analyzer import analyze_dockerfile, analyze_yaml_iac
from polaris_scanner.secrets import scan_secrets


class TestSecretsAndIac(unittest.TestCase):
    def test_secret_scanner_masks_aws_key(self) -> None:
        findings = scan_secrets(".env.test", "AWS_KEY=AKIAIOSFODNN7EXAMPLE\n")
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].masked_value.startswith("AKIA"))
        self.assertNotIn("EXAMPLE", findings[0].masked_value)

    def test_iac_dockerfile_and_yaml(self) -> None:
        df_issues = analyze_dockerfile("Dockerfile", "FROM python:latest\nENV API_KEY=123\n")
        self.assertGreaterEqual(len(df_issues), 3)
        yml_issues = analyze_yaml_iac("docker-compose.yml", "privileged: true\n")
        self.assertEqual(len(yml_issues), 1)


if __name__ == "__main__":
    unittest.main()
