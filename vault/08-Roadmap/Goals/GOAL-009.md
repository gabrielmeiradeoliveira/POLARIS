---
id: GOAL-009
title: Segurança, Autenticação, Tokens de Scanner (PAT), RBAC e Trilha de Auditoria
status: COMPLETED
priority: CRITICAL
depends_on:
  - GOAL-004
  - GOAL-007
  - GOAL-008
version_target: 0.5.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - security
  - auth
  - rbac
  - audit-log
  - tokens
---

# GOAL-009 — Segurança, Autenticação, Tokens de Scanner (PAT), RBAC e Trilha de Auditoria

## 1. Objetivo
Blindar o **POLARIS 2.0** em conformidade com as políticas do Vault (`vault/05-Security/Security-Policy.md`, `Security-Requirements.md` e `Secrets-Management.md`), ativando o modelo completo de identidade, autorização baseada em papéis (**RBAC**), autenticação de pipelines via **Personal Access Tokens (PAT)** no Scanner CLI e registro imutável de auditoria (**Audit Log**) no PostgreSQL 17.

## 2. Critérios de Aceitação
- [ ] Nenhum endpoint sensível da API v1 acessível anonimamente (exceto `/health/live`, `/health/ready` e `/api/v1/auth/login`).
- [ ] Tokens de Scanner armazenados exclusivamente via hash criptográfico e suportados via `POLARIS_TOKEN` no CLI.
- [ ] Matriz RBAC (`ADMIN`, `MAINTAINER`, `VIEWER`) e escopo `SCANNER_EXECUTE` validados por testes automatizados.
- [ ] Audit Log registrando ações administrativas e de ingestão com rastreabilidade por `request_id`.
- [ ] Evidência formal registrada em `vault/09-Validation/Reports/VAL-GOAL-009-FINAL.md` e indexada em `vault/09-Validation/Index.md`.
- [ ] `Current-State.md` atualizado para a versão `0.5.0`.
