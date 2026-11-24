---
id: VAL-GOAL-017-RELEASE-2.6.0
title: Relatório de Validação — GOAL-017 (Release 2.6.0)
status: VALIDATED
created: 2026-11-24
owner: project
tags:
  - validation
  - goal-017
  - release-2.6.0
---

# VAL-GOAL-017-RELEASE-2.6.0

## 1. Escopo Validado
- **Cache Incremental Determinístico (`src/polaris_scanner/cache.py`):** Cache SQLite em `.polaris/cache.sqlite` chaveado por `(file_sha256, rule_profile_hash, worker_version)` com flags `--no-cache` e `--clear-cache` no CLI (`src/polaris_scanner/cli.py`).
- **Paralelismo de Workers, Batching e Fast-Path Pre-Filter (`src/polaris_scanner/runner.py`, `analyzers/python/taint_engine.py`):** Execução concorrente de workers via `ThreadPoolExecutor` (`--workers <N>`), batching único por linguagem e pré-filtro `has_taint_tokens` antes da análise de fluxo de dados.
- **Calibração de Confiança & Quality Gate (`src/polaris_scanner/contracts.py`, `src/polaris_server/domain_core.py`, `src/polaris_server/gates_service.py`, `web/src/pages/IssuesPage.tsx`):** Campo `confidence` (`HIGH` / `MEDIUM` / `LOW`), suporte a `min_confidence` em `evaluate_quality_gate`, badge em `JetBrains Mono` e filtro facetado na UI.

## 2. Evidências Executadas
- `tests/performance/test_engine_benchmark.py`: 4/4 testes aprovados (`OK`), validando:
  - Cold run vs. Warm incremental run (210 arquivos, 5 modificados, 205 cache hits, `< 500ms`).
  - `0` falsos positivos em fixtures sanitizadas/limpas.
  - Contrato `IssueV1` com `confidence` e `evaluate_quality_gate` com `min_confidence`.
  - `run_workers_parallel`.
