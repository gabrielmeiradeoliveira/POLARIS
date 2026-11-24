---
id: VAL-003
title: Validação Experimental da Stack Tecnológica (GOAL-003)
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: qa
tags:
  - polaris
  - validation
  - goal-003
---

# VAL-003 — Validação Experimental da Stack Tecnológica (GOAL-003)

- **Identificador:** `GOAL-003`
- **Ambiente Utilizado:** Windows / Python 3.12.10 / SQLite 3
- **Data:** `2026-11-14`
- **Resultado Final:** `VALIDATED`

## Comandos Executados

```text
python poc/goal-003/test_poc.py
python poc/goal-003/benchmark.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validation/validate-docs.ps1
```

## Resultados Observados

### 1. Testes Automatizados e Integração Vertical (`test_poc.py`)
- `test_python_parse_error_not_treated_as_clean`: `ok`
- `test_vertical_integration_end_to_end`: `ok` (Scanner -> 4 Analisadores -> HTTP POST -> SQLite -> HTTP GET -> UI HTML)
- Total: `Ran 2 tests in 0.561s — OK`

### 2. Benchmark Real (`benchmark.py` — 200 arquivos, 50 por linguagem)
- `BENCHMARK_FILES=200`
- `BENCHMARK_ISSUES=200`
- `BENCHMARK_ELAPSED_SEC=0.1899`
- `BENCHMARK_FILES_PER_SEC=1053.33`
- `BENCHMARK_PEAK_MEM_KB=418.78`

## Artefatos Produzidos

- `poc/goal-003/analyzers.py`, `scanner.py`, `server.py`, `test_poc.py`, `benchmark.py`
- `poc/goal-003/samples/` (`app.py`, `Program.cs`, `Main.java`, `query.sql`)
- `vault/03-Architecture/Technology-Stack.md`
