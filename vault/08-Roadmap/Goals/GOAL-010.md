---
id: GOAL-010
title: Análise Incremental (New Code Period, Pull Request & Branch Diff)
status: COMPLETED
priority: HIGH
depends_on:
  - GOAL-006
  - GOAL-007
  - GOAL-008
  - GOAL-009
version_target: 0.6.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - new-code
  - pull-request
  - git-diff
  - quality-gates
  - sonarqube-parity
---

# GOAL-010 — Análise Incremental (New Code Period, Pull Request & Branch Diff)

## 1. Objetivo
Implementar o suporte completo à análise diferencial e ao conceito de **New Code Period** no **POLARIS 2.0**, permitindo avaliar separadamente **Código Novo** (*New Code*) e **Código Legado** (*Overall Code*), atingindo paridade funcional com o fluxo de Pull Requests e Branches da **SonarQube Developer Edition 2026.5 LTA** (`vault/02-Product/SonarQube-Parity.md`).

## 2. Critérios de Aceitação
- [ ] `GitDiffResolver` implementado no Scanner CLI com suporte a `--target-branch` e `--pr-key`.
- [ ] Contrato v1 estendido de forma retrocompatível com `is_new_code` e métricas diferenciais.
- [ ] Migration aplicada no PostgreSQL 17 e Quality Gates avaliando métricas `new_*` (*Clean as You Code*).
- [ ] Interface web atualizada com alternador `Código Novo` / `Código Total` e visualização de PRs dentro do design system neutro `zinc`.
- [ ] Evidência formal registrada em `vault/09-Validation/Reports/VAL-GOAL-010-FINAL.md` e indexada em `vault/09-Validation/Index.md`.
- [ ] `Current-State.md` atualizado para a versão `0.6.0`.
