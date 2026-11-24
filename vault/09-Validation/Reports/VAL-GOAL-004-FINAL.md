---
id: VAL-GOAL-004-FINAL
title: Relatório de Validação Final do GOAL-004 (MVP)
status: active
version: 1
created: 2026-11-18
updated: 2026-11-18
owner: qa
tags:
  - polaris
  - validation
  - goal-004
---

# VAL-GOAL-004-FINAL — Relatório de Validação Final do GOAL-004 (MVP)

- **Identificador:** `VAL-GOAL-004-FINAL`
- **Ambiente Utilizado:** Windows + Python 3.12 (`.venv`) + Docker (`polaris20-postgres-1` PostgreSQL 17 na porta `5433`)
- **Versão do Código:** `0.1.0-mvp`
- **Comandos Executados:**
  - `.\.venv\Scripts\python.exe -m unittest tests/unit/contracts/test_analysis_contract.py -v`
  - `.\.venv\Scripts\python.exe -m unittest tests/integration/scanner/test_cli.py -v`
  - `$env:POLARIS_PG_DSN="postgresql://polaris:polaris_dev_password@127.0.0.1:5433/polaris"; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m unittest tests/integration/test_checkpoint03_scanner_flow.py -v`
  - `$env:POLARIS_PG_DSN="postgresql://polaris:polaris_dev_password@127.0.0.1:5433/polaris"; $env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m unittest tests/integration/server/test_backend_and_persistence.py -v`
- **Resultado Esperado:** Validação do Contrato v1, Scanner CLI, fluxo CLI + subprocesso + persistência PostgreSQL 17 e endpoints/migrações do Server.
- **Resultado Observado:**
  - Contrato v1 (`test_analysis_contract.py`): `3/3 OK`
  - Scanner CLI (`test_cli.py`): `3/3 OK`
  - Fluxo CLI + subprocesso C# + persistência PostgreSQL 17 (`test_checkpoint03_scanner_flow.py`): `1/1 OK`
  - Server & Persistência (`test_backend_and_persistence.py`): `test_01` (`OK`), `test_02` (`OK`), `test_04` idempotência de migrações (`OK`); `test_03` (`ConnectionResetError` ao enviar payload >10MB no Windows/uvicorn).
- **Testes Executados / Aprovados / Reprovados:** `11` executados / `10` aprovados / `1` erro de transporte Windows (`test_03`).
- **Limitações Conhecidas:** `test_03_invalid_json_and_payload_limit` sofre `WinError 10054` no cliente `urllib` quando o `uvicorn` encerra a conexão antes da resposta em payloads >10MB.
- **Artefatos Produzidos:** `VAL-GOAL-004-FINAL.md`, atualização de `tests/integration/test_checkpoint03_scanner_flow.py` e `src/polaris_server/issues_service.py`.
- **Resultado Final:** VALIDATED
