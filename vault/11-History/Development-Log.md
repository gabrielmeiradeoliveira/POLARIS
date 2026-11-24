---
id: DOC-038
title: Log de Desenvolvimento
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: project
tags:
  - polaris
  - history
  - development-log
---

# Log de Desenvolvimento

## 2026-11-14
- **GOAL-000:** Inspeção inicial do diretório (vazio). Criação da estrutura completa do repositório (`AGENTS.md`, `.agents/`, `vault/`, arquivos raiz de governança), ADRs iniciais (`ADR-001` a `ADR-006`) e proposta do `GOAL-001`.
- **GOAL-001:** Incorporação do validador documental portátil (`scripts/validation/validate-docs.ps1`), pesquisa oficial do SonarQube Server & Community Build, especificação completa de paridade (`SonarQube-Parity.md`), inventário funcional (`REQ-FUNC-001` a `REQ-FUNC-022`), requisitos não funcionais (`REQ-NFR-001` a `REQ-NFR-013`), jornadas de usuário (`UJ-001` a `UJ-012`), matriz de rastreabilidade (`Traceability-Matrix.md`) e proposta do `GOAL-002`.
- **GOAL-002:** Auditoria do `GOAL-001` (referência SonarQube Server 2026.5 LTA), definição da arquitetura completa (Scanner, Analisadores, Contrato, Monólito Modular com 18 módulos, Modelo de Domínio, Persistência, API/Dashboard, Threat Model, Testes, Implantação e Rastreabilidade), `ADR-007` a `ADR-011` (`PROPOSED`) e proposta do `GOAL-003`.
- **GOAL-003:** Prova de conceito executável em `poc/goal-003/` (Scanner, 4 analisadores, servidor HTTP, SQLite, UI mínima), testes de integração vertical (`2/2 OK`) e benchmark (`200` arquivos em `0.1899s`, `1053.33 arq/s`, `418.78 KB` pico). Proposta do `GOAL-004`.
- **GOAL-003-R1:** Reabertura e auditoria do `GOAL-003`. Inventário real do ambiente identificou ausência de `mvn`, `gradle`, `go`, `psql` e bloqueio de rede no sandbox para pacotes externos (Roslyn, JDT/JavaParser, LibCST/Astroid, SQLGlot/ScriptDom, React/Vue). Estado atualizado para `BLOCKED` com instruções de desbloqueio em `VAL-GOAL-003-R1.md`.
- **GOAL-003-R2:** Retomada após preparação do ambiente. Validados os 4 analisadores especializados reais (Python `libcst`+`astroid`, C# Roslyn `4.11.0`, Java `javaparser-symbol-solver-core` `3.26.2` via Maven Docker, SQL `sqlglot` `25.32.1`), 20 regras experimentais (`Precision=1.0`, `Recall=1.0`, `F1=1.0` no corpus experimental) e PostgreSQL 17 via Docker Compose. Todos os Gates A–F aprovados (`VAL-GOAL-003-R2.md`).
- **GOAL-003-R3:** Fechamento completo dos Gates D, E e F. Integração vertical ponta a ponta (`Scanner` -> 4 analisadores -> `FastAPI` -> `PostgreSQL 17` -> API -> `React + TypeScript`), testes de segurança (`3/3 OK`), benchmark com RSS real (`2.3972s` mediana, `29.02 MB` RSS) e stack recomendada consolidada em `Technology-Stack.md`.
- **GOAL-004:** Aprovação dos `ADR-007` a `ADR-011` e da stack em `Technology-Stack.md`. Implementação do núcleo definitivo em `src/polaris_server/`, `src/polaris_scanner/`, `infra/docker-compose.yml` e `tests/test_foundation.py` (`2/2 OK` contra PostgreSQL 17).
- **GOAL-004-B (`2026-11-15`):** Reabertura do `GOAL-004` (`IN_PROGRESS`), revisão da auditoria (`AUDIT-GOAL-004-R1.md`), criação da governança verificável (`acceptance.schema.json`, `GOAL-004-B.json`, `validate_goals.py` com 7/7 testes), validação completa do backend FastAPI (`3/3` unitários + `4/4` integração PostgreSQL 17 + `2/2` fundação).

## 2026-11-15 — GOAL-004-C: Scanner Definitivo e Contratos Compartilhados

- **Status:** `COMPLETED` (29/29 critérios `PASS` em `vault/09-Validation/Acceptance/GOAL-004-C.json`). `GOAL-004` principal mantido em `IN_PROGRESS`.
- **Entregas:** Modularização de `src/polaris_scanner/` (`config.py`, `discovery.py`, `registry.py`, `executor.py`, `contracts.py`, `cli.py`) e suítes permanentes em `tests/unit/scanner/`, `tests/unit/contracts/`, `tests/contract/` e `tests/integration/scanner/`.
- **Evidências:** `18/18` novos testes aprovados + `2/2` em `tests/test_foundation.py`, registrados em `vault/09-Validation/Reports/VAL-GOAL-004-C.md`.

## 2026-11-18 — Encerramento do GOAL-004 (MVP `0.1.0-mvp`) e Início do GOAL-006

- **Status:** `GOAL-004` marcado como `COMPLETED` (`0.1.0-mvp`); `GOAL-006` promovido para `IN_PROGRESS`.
- **Entregas Validadas:** Núcleo do POLARIS Server, Scanner CLI, persistência relacional PostgreSQL 17 (migrações idempotentes) e Contrato de Análise v1 (`ADR-010`).
- **Evidências:** Registradas em `vault/09-Validation/Reports/VAL-GOAL-004-FINAL.md` e `vault/09-Validation/Index.md`.

## 2026-11-18 — Release POLARIS `2.0.0` (`GOAL-006` a `GOAL-011`)

- **Status:** `2.0.0` (`RELEASED / STABLE`).
- **Entregas Consolidadas:** Analisadores multi-linguagem (`Python`, `C#`, `Java`, `SQL`) com transporte `gzip`, Quality Gates e `--fail-on-quality-gate`, Design System neutro (`zinc`), segurança/RBAC, `GitDiffResolver` (`--target-branch`, `--pr-key`), `/metrics` e runbooks em `vault/10-Operations/`.
- **Evidências:** `VAL-GOAL-011-RELEASE-2.0.0.md` (`14/14 OK` na suíte de regressão).

## 2026-11-18 — Releases POLARIS `2.1.0` (`GOAL-012`) e `2.2.0` (`GOAL-013`)

- **Status:** `2.2.0` (`RELEASED / STABLE`).
- **Entregas Consolidadas:** Catálogo expandido de regras (`GOAL-012`, `6/6 OK`), CFG intra-procedural e Taint Analysis multi-arquivo em Python, C# (Roslyn) e Java (JavaParser) (`GOAL-013`, `4/4 OK`).
- **Evidências:** `VAL-GOAL-012-RELEASE-2.1.0.md` e `VAL-GOAL-013-RELEASE-2.2.0.md`.
