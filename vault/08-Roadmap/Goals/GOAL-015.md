---
id: GOAL-015
title: Analisador Full-Stack (TypeScript/React), Infraestrutura (Dockerfile/YAML) e Secret Scanner
status: PLANNED
priority: HIGH
depends_on:
  - GOAL-012
  - GOAL-014
version_target: 2.4.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - release-2.4.0
  - typescript
  - react
  - iac
  - dockerfile
  - secret-detection
---

# GOAL-015 — Analisador Full-Stack (TypeScript/React), IaC e Secret Scanner (`2.4.0`)

## 1. Objetivo
Expandir a cobertura do **POLARIS** para auditar repositórios modernos de ponta a ponta (Frontend + Infraestrutura + Segredos) em uma única execução do `polaris-scanner`, habilitando inclusive a auto-análise completa do diretório `web/` do próprio POLARIS.

## 2. Critérios de Aceitação
- [ ] Worker TypeScript/React validado com `>= 20` regras e executado em dogfooding sobre `web/src/` do próprio POLARIS.
- [ ] Regras de `Dockerfile` e YAML validadas contra `Dockerfile` e `docker-compose.yml` reais.
- [ ] Secret Scanner validado com chaves sintéticas (garantindo mascaramento total no relatório JSON e no PostgreSQL).
- [ ] Evidência registrada em `vault/09-Validation/Reports/VAL-GOAL-015-RELEASE-2.4.0.md` e `Current-State.md` atualizado para `2.4.0`.
