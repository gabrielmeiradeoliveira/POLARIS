---
id: VAL-POLARIS-2.1-MASTER
title: Relatório de Evolução — POLARIS 2.1 (GOAL-021-034-MASTER)
type: validation-report
status: IN_PROGRESS
created_at: 2026-11-15
updated_at: 2026-11-15
tags: [polaris-2.1, evolution, taint, semantic, incremental]
---

# Relatório de Evolução — POLARIS 2.1

## 1. Comparação de Capacidades

| Capacidade | Versão Anterior (2.0) | POLARIS 2.1 | Evidência |
| :--- | :--- | :--- | :--- |
| Descoberta de Projeto | Arquivos isolados | `ProjectManifest` com hashes SHA-256 e metadados | `src/polaris_scanner/project_manifest.py` |
| Taint Analysis Python | Busca sintática | Fluxo intraprocedural (`SOURCE -> PROPAGATION -> SINK`) com sanitizers | `analyzers/python/taint_engine.py` |
| Semântica SQL | AST por statement | Resolução de aliases, CTEs, schema estático e column lineage | `analyzers/sql/semantic_engine.py` |
| Cache Incremental | Inexistente | Chave por hash de conteúdo, versão e perfil | `src/polaris_scanner/incremental_cache.py` |

## 2. Testes Executados
- `tests/integration/test_polaris_2_1_engines.py`: `3/3 OK` (`0.128s`).
- `scripts/validation/validate_goals.py`: `ACCEPTANCE_ERRORS=0`.
- `scripts/validation/validate-docs.ps1`: `BROKEN_LINKS_COUNT=0`.
