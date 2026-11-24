---
id: VAL-GOAL-007-FINAL
title: Relatório de Validação do GOAL-007 (Quality Gates, Ratings e Quality Profiles)
status: active
version: 1
created: 2026-11-18
updated: 2026-11-18
owner: qa
tags:
  - polaris
  - validation
  - goal-007
---

# VAL-GOAL-007-FINAL — Relatório de Validação do GOAL-007

- **Identificador:** `VAL-GOAL-007-FINAL`
- **Ambiente Utilizado:** Windows + Python 3.12 (`.venv`) + Docker (`polaris20-postgres-1` PostgreSQL 17 na porta `5433`)
- **Versão do Código:** `0.3.0`
- **Comandos Executados:**
  - `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m unittest tests/unit/analyzers/test_python_analyzer.py tests/unit/analyzers/test_csharp_analyzer.py tests/unit/analyzers/test_java_analyzer.py tests/unit/analyzers/test_sql_analyzer.py -v`
  - `$env:POLARIS_PG_DSN="postgresql://polaris:polaris_dev_password@127.0.0.1:5433/polaris"; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m unittest tests/test_gates_evaluation.py -v`
- **Resultado Esperado:** Suíte unitária dos 4 analisadores 100% verde (incluindo `JV-REL-008` em Java), avaliação de Quality Gates aprovada e flag `--fail-on-quality-gate` (`exit_code = 3`) integrada ao Scanner CLI.
- **Resultado Observado:**
  - `test_python_analyzer.py`, `test_csharp_analyzer.py`, `test_java_analyzer.py`, `test_sql_analyzer.py`: `4/4 OK` (`0.812s`).
  - `test_gates_evaluation.py`: `4/4 OK`.
  - `src/polaris_scanner/cli.py`: flag `--fail-on-quality-gate` implementada retornando `exit_code = 3` quando `quality_gate.status == "FAILED"`.
- **Artefatos Produzidos:** `tests/unit/analyzers/test_java_analyzer.py`, `src/polaris_scanner/cli.py`, `VAL-GOAL-007-FINAL.md`.
- **Resultado Final:** VALIDATED
