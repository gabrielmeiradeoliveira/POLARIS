---
id: GOAL-012
title: Expansão Profunda de Regras, Detector de Duplicação (CPD), Cobertura de Testes e Ciclo de Vida de Issues
status: IN_PROGRESS
priority: HIGH
depends_on:
  - GOAL-011
version_target: 2.1.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - release-2.1.0
  - analyzers
  - cpd
  - coverage
  - issue-lifecycle
  - nosonar
---

# GOAL-012 — Expansão Profunda de Regras, CPD, Cobertura de Testes e Ciclo de Vida de Issues (`2.1.0`)

## 1. Objetivo
Elevar a profundidade analítica e operacional do **POLARIS 2.x** para o padrão completo de governança do **SonarQube Developer Edition 2026.5 LTA** (`vault/02-Product/SonarQube-Parity.md`):
1. Catálogo de 100+ regras determinísticas (25+ por linguagem: Python, C#, Java, SQL).
2. Detector de Duplicação de Código (CPD).
3. Ingestão de Cobertura de Testes (`coverage` / `new_coverage`).
4. Ciclo de Vida de Issues & Supressão Inline (`NOSONAR` / `polaris:ignore`).

## 2. Critérios de Aceitação
- [ ] Catálogo de regras (`>= 100` regras) validado.
- [ ] CPD e Coverage operacionais.
- [ ] Ciclo de vida de issues e supressão inline validados.
- [ ] Evidência formal registrada em `vault/09-Validation/Reports/VAL-GOAL-012-RELEASE-2.1.0.md`, indexada em `vault/09-Validation/Index.md` e `Current-State.md` atualizado para `2.1.0`.
