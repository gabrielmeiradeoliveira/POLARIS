"""End-to-End Integration Tests for POLARIS v1.6 (GOALs 44, 45, 46).

Tests the integration of:
- GOAL 44: Container & Supply Chain deterministic security scanners in `polaris review`
- GOAL 45: Native SARIF v2.1.0 output formatting via `--format sarif`
- GOAL 46: Declarative Quality Gate enforcement (polaris.yaml) and exit codes (0, 1, 2)
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from polaris.cli import app
from polaris.core.errors import ExitCode
from tests.conftest import run_git_cmd

runner = CliRunner()


def test_v16_integrated_scanners_dockerfile(temp_git_repo: Path) -> None:
    """GOAL 44: Verify Dockerfile defects are detected during polaris review."""
    df = temp_git_repo / "Dockerfile"
    df.write_text(
        "FROM python:latest\nRUN curl -sSL https://install.python-poetry.org | bash\nCMD [\"python\", \"app.py\"]\n",
        encoding="utf-8",
    )
    run_git_cmd(temp_git_repo, "add", "Dockerfile")
    run_git_cmd(temp_git_repo, "commit", "-m", "add dockerfile")

    # Modify Dockerfile to create a diff
    df.write_text(
        "FROM python:latest\nRUN curl -sSL https://install.python-poetry.org | bash\nENV API_KEY='secret12345678'\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["review", "--provider", "fake", "--repo", str(temp_git_repo)])
    assert result.exit_code == 0
    assert "Additional Security Scanner Findings:" in result.stdout
    assert "Dockerfile" in result.stdout
    assert "INSECURE_CURL_BASH" in result.stdout or "HARDCODED_SECRET" in result.stdout


def test_v16_sarif_output_format(temp_git_repo: Path) -> None:
    """GOAL 45: Verify --format sarif produces valid SARIF v2.1.0 JSON."""
    calc_file = temp_git_repo / "src" / "calc.py"
    calc_file.write_text("def div(a, b):\n    return a / 0\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["review", "--provider", "fake", "--format", "sarif", "--repo", str(temp_git_repo)],
    )
    # Default policy fails on HIGH/CRITICAL if finding is high, or succeeds if tolerated
    # Regardless of exit code, stdout must contain valid SARIF JSON
    payload = json.loads(result.stdout)
    assert payload["version"] == "2.1.0"
    assert "$schema" in payload
    assert "runs" in payload
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["tool"]["driver"]["name"] == "POLARIS"


def test_v16_quality_gate_policy_file(temp_git_repo: Path) -> None:
    """GOAL 46: Verify polaris.yaml policy evaluation and exit codes."""
    calc_file = temp_git_repo / "src" / "calc.py"
    calc_file.write_text("def div(a, b):\n    return a / 0\n", encoding="utf-8")

    # 1. With permissive policy (max_tolerated_vulnerabilities: 10), it should PASS with code 0
    policy_file = temp_git_repo / "polaris.yaml"
    policy_file.write_text(
        "policy:\n  fail_on_severity: [CRITICAL]\n  max_tolerated_vulnerabilities: 10\n",
        encoding="utf-8",
    )

    res_pass = runner.invoke(
        app,
        ["review", "--provider", "fake", "--repo", str(temp_git_repo)],
    )
    assert res_pass.exit_code == int(ExitCode.SUCCESS)

    # 2. With strict policy (max_tolerated_vulnerabilities: 0, fail_on_severity: [HIGH]), it should FAIL with code 1
    policy_file.write_text(
        "policy:\n  fail_on_severity: [HIGH, CRITICAL]\n  max_tolerated_vulnerabilities: 0\n",
        encoding="utf-8",
    )
    res_fail = runner.invoke(
        app,
        ["review", "--provider", "fake", "--repo", str(temp_git_repo)],
    )
    assert res_fail.exit_code == 1
    assert "POLARIS QUALITY GATE" in res_fail.stderr


def test_v16_config_error_exit_code(temp_git_repo: Path) -> None:
    """Verify exit code 2 on configuration error (e.g. invalid provider)."""
    res = runner.invoke(
        app,
        ["review", "--provider", "invalid_prov", "--repo", str(temp_git_repo)],
    )
    assert res.exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert res.exit_code == 2
