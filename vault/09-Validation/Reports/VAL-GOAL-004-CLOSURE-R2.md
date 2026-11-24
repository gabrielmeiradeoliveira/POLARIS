---
id: VAL-GOAL-004-CLOSURE-R2
title: Relatório de Encerramento — GOAL-004-CLOSURE-R2
type: validation-report
status: COMPLETED
created_at: 2026-11-15
updated_at: 2026-11-15
tags: [validation, goal-004, closure-r2, e2e, security]
---

# Relatório de Encerramento — GOAL-004-CLOSURE-R2

## 1. Correções Realizadas (P0)

1. **Dependências Python (`pip-audit`):**
   - Anterior: `fastapi==0.115.6` / `starlette==0.41.3` (7 CVEs em `starlette`).
   - Atual: `fastapi==0.163.1`, `starlette==1.10.0`, `uvicorn==0.54.0` (atualizado no `.venv` e em `infra/docker/Dockerfile.server`).
   - Resultado `pip-audit`: `No known vulnerabilities found` (`exit 0`).
2. **Integração Frontend/Backend e Proxy Reverso:**
   - Causa real da falha anterior: (a) `polaris-def-server-1` usava `DATABASE_URL` em vez de `POLARIS_PG_DSN`, causando `503` em `/health/ready`; (b) `App.tsx` não renderizava `<main>` em estado de erro e esperava `project_key` em vez de `projectKey` dentro de `{ projects: [...] }`.
   - Correção: Adicionado `POLARIS_PG_DSN` em `docker-compose.yml`, proxy reverso `nginx.conf` (`/api/` e `/health/` na mesma origem `http://127.0.0.1:5173`), `<main>` sempre presente em `App.tsx` e `projectKey` alinhado ao contrato da API.

## 2. Evidências de Runtime e E2E

- **Docker Compose (`polaris-def`):** `polaris-def-postgres-1` (`healthy`, `5433->5432`), `polaris-def-server-1` (`healthy`, `8000->8000`), `polaris-def-web-1` (`Up`, `5173->80`).
- **Playwright Chromium Real (`tests/e2e`):** `2/2 OK` (`4.105s`), cobrindo navegação real e pipeline completo `Scanner -> 4 Analisadores -> Contrato JSON -> FastAPI -> PostgreSQL -> Navegador`.
- **Qualidade e Cobertura:** Ruff (`All checks passed!`), Mypy (`0` issues em 7 arquivos), Coverage Python (`74%` em `462` statements / `156` branches), `npm audit --omit=dev` (`0` vulnerabilidades).
- **Benchmark:** `40` arquivos: mediana `1.2419s` (`32.21 files/s`); `200` arquivos: mediana `1.4186s` (`140.98 files/s`).
