---
id: VAL-GOAL-018-RELEASE-2.6.1
title: Relatório de Validação — GOAL-018 (Release 2.6.1)
status: VALIDATED
created: 2026-11-24
owner: project
tags:
  - validation
  - goal-018
  - release-2.6.1
---

# VAL-GOAL-018-RELEASE-2.6.1

- **Cache `.json.gz` atômico:** `src/polaris_scanner/cache.py` (sem SQLite), leitura única de disco, descarte seguro de binários e minificados (`.js`/`.mjs`/`.css`) sem pular backend por linha longa.
- **Modo Dev & Prioridade:** `--profile auto|low-spec|max`, `--max-file-size`, `--include-minified`, `--changed-only`, prioridade reduzida em subprocessos (`executor.py`), entropia fatiada (`secrets.py`).
- **Suíte de Testes:** 11/11 testes aprovados (`test_monolith_safety.py`, `test_engine_benchmark.py`, `test_low_spec_envelope.py`, `test_go_python_parity.py`).
