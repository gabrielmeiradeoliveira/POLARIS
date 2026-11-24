---
id: GOAL-008
title: Interface Web Operacional (React 18 + TypeScript + Vite) com Design System Profissional
status: COMPLETED
priority: HIGH
depends_on:
  - GOAL-004
  - GOAL-006
  - GOAL-007
version_target: 0.4.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - frontend
  - design-system
  - react
  - typescript
  - ux-ui
  - anti-ai-slop
---

# GOAL-008 — Interface Web Operacional (React 18 + TypeScript + Vite)

## 1. Objetivo
Construir e integrar a interface web oficial do **POLARIS 2.0** (`React 18 + TypeScript + Vite`, servida na porta `5173`), conectada integralmente à **API v1** do POLARIS Server (`PostgreSQL 17`), entregando visibilidade operacional de projetos, análises, issues, métricas de código, Quality Gates e Quality Profiles com rigor visual de produto de engenharia de software de nível enterprise (Zero AI Slop, paleta neutra zinc/neutral, Dark/Light mode, `tabular-nums`, `JetBrains Mono`).

## 2. Critérios de Aceitação
- [ ] Todas as 6 visões operacionais implementadas e conectadas aos endpoints reais da API v1 do POLARIS Server.
- [ ] Auditoria visual aprovada: zero gradientes roxo/azul, zero cards decorativos redundantes, `tabular-nums`, fonte monoespaçada e Dark/Light mode.
- [ ] `tsc -b` e `npm run build` concluídos com sucesso.
- [ ] Evidência formal registrada em `vault/09-Validation/Reports/VAL-GOAL-008-FINAL.md` e indexada em `vault/09-Validation/Index.md`.
- [ ] `Current-State.md` atualizado para a versão `0.4.0`.
