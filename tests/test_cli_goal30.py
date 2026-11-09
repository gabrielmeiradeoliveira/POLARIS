"""Tests for CLI and JSON Explainability compatibility (GOAL 30 - Fase 30.13)."""

import json
from typer.testing import CliRunner
from polaris.cli import app

runner = CliRunner()


def test_cli_version_and_help_compatibility():
    """Verify standard CLI contracts are fully preserved."""
    res_v = runner.invoke(app, ["--version"])
    assert res_v.exit_code == 0
    assert "polaris" in res_v.stdout

    res_h = runner.invoke(app, ["--help"])
    assert res_h.exit_code == 0
    assert "POLARIS" in res_h.stdout
    assert "review" in res_h.stdout
