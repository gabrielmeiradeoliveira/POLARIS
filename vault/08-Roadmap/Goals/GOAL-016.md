---
id: GOAL-016
title: Auditoria de Dependências (SCA via OSV) e Pull Request Decoration (GitHub / GitLab)
status: PLANNED
priority: HIGH
depends_on:
  - GOAL-010
  - GOAL-012
  - GOAL-015
version_target: 2.5.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - release-2.5.0
  - sca
  - dependencies
  - osv
  - pr-decoration
  - github
  - gitlab
---

# GOAL-016 — Auditoria de Dependências (SCA via OSV) e Pull Request Decoration (`2.5.0`)

## 1. Objetivo
Fechar a paridade funcional completa da linha **POLARIS 2.x** adicionando **Software Composition Analysis (SCA)** para detectar vulnerabilidades conhecidas (CVEs) em dependências de terceiros e **PR Decoration** nativa para publicar o veredito do Quality Gate e comentários inline diretamente em Pull Requests / Merge Requests no **GitHub** e **GitLab**.

## 2. Critérios de Aceitação
- [ ] Parsers SCA validados para Python, .NET, Java e Node com fixtures contendo CVEs conhecidos (e teste em modo offline com mock/fixture local).
- [ ] Decorador de PR validado com mocks HTTP completos das APIs do GitHub e GitLab (verificando criação de comentário resumo, comentários inline no diff e atualização idempotente em re-push).
- [ ] Evidência registrada em `vault/09-Validation/Reports/VAL-GOAL-016-RELEASE-2.5.0.md`, indexada em `vault/09-Validation/Index.md` e `Current-State.md` atualizado para `2.5.0`.
