"""Tests for expanded Security Intelligence Engine (GOAL 30 - Fase 30.6)."""

import ast
from polaris.guardrails.authorization import analyze_function_authorization_relaxation


def test_sec_path_traversal_detection():
    """Verify detection of path traversal sequences introduced in file access calls."""
    before_code = """
def load_template(filename: str):
    return open(f"/templates/{filename}").read()
"""
    after_code = """
def load_template(filename: str):
    return open(f"/templates/../{filename}").read()
"""
    before_fn = ast.parse(before_code).body[0]
    after_fn = ast.parse(after_code).body[0]

    findings = analyze_function_authorization_relaxation(
        before_func=before_fn,
        after_func=after_fn,
        file_path="views/renderer.py",
    )

    assert len(findings) >= 1
    assert any(f.rule_id == "SEC-PATH-001" for f in findings)
