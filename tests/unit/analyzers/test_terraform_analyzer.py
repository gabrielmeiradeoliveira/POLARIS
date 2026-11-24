from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "terraform"))

from polaris_tf_analyzer import analyze_tf_content


class TestTerraformAnalyzer(unittest.TestCase):
    def test_positive_all_10_rules(self) -> None:
        tf = """
        resource "aws_db_instance" "db" {
          password            = "SuperSecret123!"
          publicly_accessible = true
          storage_encrypted   = false
          enable_logging      = false
        }
        resource "aws_security_group" "sg" {
          ingress { cidr_blocks = ["0.0.0.0/0"] }
        }
        resource "aws_s3_bucket" "b" {
          acl = "public-read"
        }
        data "aws_iam_policy_document" "p" {
          statement { actions = ["*"] }
        }
        resource "aws_lb_listener" "l" {
          protocol = "HTTP"
        }
        terraform {
          required_providers { aws = { source = "hashicorp/aws" } }
        }
        """
        ids = {i["ruleId"].split(":")[1] for i in analyze_tf_content(tf)}
        expected = {
            "TF-SEC-001", "TF-SEC-002", "TF-SEC-003", "TF-SEC-004",
            "TF-SEC-005", "TF-SEC-006", "TF-SEC-007", "TF-SEC-008",
            "TF-REL-001", "TF-REL-002",
        }
        self.assertEqual(ids, expected)

    def test_negative_safe_terraform(self) -> None:
        safe_tf = """
        terraform {
          required_providers { aws = { source = "hashicorp/aws", version = "~> 5.0" } }
        }
        resource "aws_db_instance" "db" {
          publicly_accessible = false
          storage_encrypted   = true
          lifecycle { prevent_destroy = true }
        }
        """
        self.assertEqual(analyze_tf_content(safe_tf), [])


if __name__ == "__main__":
    unittest.main()
