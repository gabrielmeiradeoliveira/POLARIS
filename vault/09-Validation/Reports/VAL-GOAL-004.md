---
id: VAL-004
title: Validação da Fundação Executável (GOAL-004)
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: qa
tags:
  - polaris
  - validation
  - goal-004
---

# VAL-GOAL-004 — Validação da Fundação Executável

- **Identificador:** `GOAL-004`
- **Ambiente Utilizado:** Windows / Python 3.12.10 / PostgreSQL 17
- **Data:** `2026-11-14`
- **Resultado Final:** `VALIDATED`

## Comandos Executados

```text
.\.venv\Scripts\python.exe tests/test_foundation.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validation/validate-docs.ps1
```

## Resultados Observados

- `test_scanner_discovery_and_exclusions`: `ok`
- `test_server_projects_and_analyses_postgresql`: `ok` (criação de projeto `201`, duplicado `409`, ingestão `201` e consulta no PostgreSQL 17)
- Total: `Ran 2 tests in 0.711s — OK`

## Artefatos de Produto Produzidos

- `pyproject.toml`
- `infra/docker-compose.yml`
- `src/polaris_server/` (`config.py`, `db.py`, `api.py`)
- `src/polaris_scanner/` (`cli.py`)
- `tests/test_foundation.py`
