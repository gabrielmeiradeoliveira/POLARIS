---
id: DOC-034
title: Índice de Validações
status: active
version: 1
created: 2026-11-14
updated: 2026-11-17
owner: qa
tags:
  - polaris
  - validation
  - index
---

# Índice de Validações e Evidências

Este diretório armazena relatórios formais de validação (`Reports/`) e evidências coletadas (`Evidence/`).

## Validações Registradas

- [VAL-GOAL-000](Reports/VAL-GOAL-000.md) — Validação documental do `GOAL-000` (`VALIDATED` em `2026-11-14`).
- [VAL-GOAL-000-COMPLEMENT](Reports/VAL-GOAL-000-COMPLEMENT.md) — Validação complementar com validador portátil (`VALIDATED` em `2026-11-14`).
- [VAL-GOAL-001](Reports/VAL-GOAL-001.md) — Validação documental do `GOAL-001` (`VALIDATED` em `2026-11-14`).
- [VAL-GOAL-002](Reports/VAL-GOAL-002.md) — Validação documental e semântica do `GOAL-002` (`VALIDATED` em `2026-11-14`).
- [VAL-GOAL-003](Reports/VAL-GOAL-003.md) — Validação experimental da stack tecnológica (`VALIDATED` em `2026-11-14`).
- [AUDIT-POC-GOAL-003](Reports/AUDIT-POC-GOAL-003.md) — Auditoria técnica da PoC `poc/goal-003/` (`2026-11-14`).
- [VAL-GOAL-003-R1](Reports/VAL-GOAL-003-R1.md) — Reavaliação do `GOAL-003` (`BLOCKED` em `2026-11-14`).
- [VAL-GOAL-003-R2](Reports/VAL-GOAL-003-R2.md) — Validação experimental completa do `GOAL-003-R2` (`VALIDATED` em `2026-11-14`).
- [VAL-GOAL-003-R3](Reports/VAL-GOAL-003-R3.md) — Fechamento dos gates D, E e F (`VALIDATED` em `2026-11-14`).
- [VAL-GOAL-004](Reports/VAL-GOAL-004.md) — Validação da fundação executável (`VALIDATED` em `2026-11-14`).
- [VAL-GOAL-004-R1](Reports/VAL-GOAL-004-R1.md) — Validação completa dos Gates A–J (`VALIDATED` em `2026-11-14`).
- [AUDIT-GOAL-004](Reports/AUDIT-GOAL-004.md) — Auditoria independente da fundação (`GOAL-004-A` em `2026-11-14`).
- [AUDIT-GOAL-004-R1](Reports/AUDIT-GOAL-004-R1.md) — Revisão complementar da auditoria (`2026-11-15`).
- [VAL-GOAL-004-B](Reports/VAL-GOAL-004-B.md) — Validação do `GOAL-004-B` (`VALIDATED` em `2026-11-15`).
- **Verificação de Núcleo (2026-11-17):** Contrato v1 (`tests/unit/contracts/test_analysis_contract.py`, 3/3 `OK`) e Scanner CLI (`tests/integration/scanner/test_cli.py`, 3/3 `OK`) validados; testes dependentes de PostgreSQL 17 (`test_backend_and_persistence.py` e `test_checkpoint03_scanner_flow.py`) bloqueados porque o daemon do Docker Desktop não está em execução no host.
- [VAL-GOAL-004-FINAL](Reports/VAL-GOAL-004-FINAL.md) — Validação final do `GOAL-004` (`0.1.0-mvp`) contra PostgreSQL 17 (`10/11 OK`: Contrato v1 `3/3`, CLI `3/3`, Fluxo C# + PostgreSQL `1/1`, Server `3/4`; `VALIDATED` em `2026-11-18`).
- [VAL-GOAL-006-FINAL](Reports/VAL-GOAL-006-FINAL.md) — Validação do `GOAL-006` (`0.2.0`): smoke test 4 linguagens (`1/1 OK`), analisadores Python/C#/SQL (`3/3 OK`), transporte `gzip` e E2E polyglot (`1/1 OK`, `VALIDATED` em `2026-11-18`).
- [VAL-GOAL-007-FINAL](Reports/VAL-GOAL-007-FINAL.md) — Validação do `GOAL-007` (`0.3.0`): 4 analisadores unitários (`4/4 OK`), Quality Gates (`4/4 OK`) e flag `--fail-on-quality-gate` (`VALIDATED` em `2026-11-18`).
- [VAL-GOAL-008-FINAL](Reports/VAL-GOAL-008-FINAL.md) — Validação do `GOAL-008` (`0.4.0`): `tsc -b && vite build` (`439ms`, `44 modules`) e tokens neutros zinc/neutral (`VALIDATED` em `2026-11-18`).
- [VAL-GOAL-009-FINAL](Reports/VAL-GOAL-009-FINAL.md) — Validação do `GOAL-009` (`0.5.0`): hashing de senhas, RBAC e controles de segurança (`5/5 OK`, `1 skipped`; `VALIDATED` em `2026-11-18`).
- [VAL-GOAL-010-FINAL](Reports/VAL-GOAL-010-FINAL.md) — Validação do `GOAL-010` (`0.6.0`): equivalência incremental (`1/1 OK`) e `GitDiffResolver` (`1/1 OK`; `VALIDATED` em `2026-11-18`).
- [VAL-GOAL-011-RELEASE-2.0.0](Reports/VAL-GOAL-011-RELEASE-2.0.0.md) — Validação Final da Release `2.0.0` (`14/14 OK` na suíte de regressão; `VALIDATED` em `2026-11-18`).
- [VAL-GOAL-012-RELEASE-2.1.0](Reports/VAL-GOAL-012-RELEASE-2.1.0.md) — Validação Final da Release `2.1.0` (`6/6 OK`; `VALIDATED` em `2026-11-18`).
- [VAL-GOAL-013-RELEASE-2.2.0](Reports/VAL-GOAL-013-RELEASE-2.2.0.md) — Validação Final da Release `2.2.0` (`4/4 OK` em CFG & Taint Analysis multi-arquivo; `VALIDATED` em `2026-11-18`).
- [VAL-GOAL-014-RELEASE-2.3.0](Reports/VAL-GOAL-014-RELEASE-2.3.0.md) — Validação Final da Release `2.3.0` (`1/1 OK` em Issue Relocation 4 estágios; `VALIDATED` em `2026-11-18`).
- [VAL-GOAL-015-RELEASE-2.4.0](Reports/VAL-GOAL-015-RELEASE-2.4.0.md) — Validação Final da Release `2.4.0` (`2/2 OK` em Secret Scanner & IaC; `VALIDATED` em `2026-11-18`).
- [VAL-GOAL-016-RELEASE-2.5.0](Reports/VAL-GOAL-016-RELEASE-2.5.0.md) — Validação Final da Release `2.5.0` (`2/2 OK` em SCA & PR Decoration; `VALIDATED` em `2026-11-18`).
