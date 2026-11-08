"""End-to-end integration test verifying GOAL 30 code intelligence via public CLI."""

import json
from pathlib import Path
from typer.testing import CliRunner

from polaris.cli import app

runner = CliRunner()


def test_cli_hybrid_end_to_end_triggers_goal30_intelligence(tmp_path: Path):
    """Verify that running 'polaris review --strategy hybrid' executes GOAL 30 engines and populates JSON."""
    # 1. Create a git repo fixture with cross-file dependency and dangerous dataflow
    import subprocess

    def run_git(*args):
        subprocess.check_call(["git", *args], cwd=tmp_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    run_git("init")
    run_git("config", "user.email", "dev@polaris.local")
    run_git("config", "user.name", "Polaris Dev")

    # Initial commit (clean)
    service_file = tmp_path / "service.py"
    service_file.write_text("def query_db(uid: int): pass\n", encoding="utf-8")
    run_git("add", ".")
    run_git("commit", "-m", "initial commit")

    # Working tree modification: introduce dataflow taint and contract breakage
    service_file.write_text(
        "def query_db(request, new_required_arg: str):\n"
        "    uid = request.args['id']\n"
        "    cursor.execute(f'SELECT * FROM users WHERE id = {uid}')\n",
        encoding="utf-8",
    )

    # Execute CLI review with --strategy hybrid and --format json
    res = runner.invoke(
        app,
        [
            "review",
            "--repo", str(tmp_path),
            "--provider", "fake",
            "--strategy", "hybrid",
            "--format", "json",
            "--no-allow-external",
        ],
    )

    assert res.exit_code == 0
    # Confirm output contains valid JSON and GOAL 30 intelligence section
    parsed = json.loads(res.stdout[res.stdout.find("{"):])
    assert "goal30_intelligence" in parsed
    assert parsed["goal30_intelligence"] is not None
    analyses = parsed["goal30_intelligence"]["analyses"]
    assert len(analyses) >= 1
    analysis = analyses[0]
    assert analysis["file_path"] == "service.py"
    assert analysis["dataflow_count"] >= 1
    assert len(analysis["fused_evidences"]) >= 1
    assert len(analysis["risk_scores"]) >= 1
