---
id: GOAL-007
title: Motor de Quality Gates, Cálculo de Ratings e Quality Profiles
status: COMPLETED
priority: HIGH
depends_on:
  - GOAL-006
version_target: 0.3.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - quality-gates
  - ratings
  - quality-profiles
  - sonarqube-parity
---

# GOAL-007 — Motor de Quality Gates, Cálculo de Ratings e Quality Profiles

## 1. Objetivo
Implementar a camada de governança de qualidade de código e decisão automatizada do **POLARIS 2.0**, atingindo paridade funcional com o fluxo de avaliação do **SonarQube Developer Edition 2026.5 LTA** (`vault/02-Product/SonarQube-Parity.md`):
1. **Cálculo Determinístico de Ratings (`A` a `E`)** para *Reliability* (Bugs), *Security* (Vulnerabilities) e *Maintainability* (Technical Debt Ratio / Code Smells).
2. **Motor de Avaliação de Quality Gates (`PASSED` / `FAILED`)** executado automaticamente ao final da ingestão de cada análise, com suporte ao modo CI/CD (`--fail-on-quality-gate` / `exit_code = 3`).
3. **Gerenciamento de Quality Profiles** permitindo ativar/desativar regras e sobrescrever severidades por linguagem e projeto.

## 2. Saneamento Técnico Herdado do GOAL-006
- [ ] Ajuste em `tests/unit/analyzers/test_java_analyzer.py` para contemplar `JV-REL-008` (além de `JV-SYN-001` e `JV-SEM-001`).

## 3. Critérios de Aceitação
- [ ] Teste unitário Java (`test_java_analyzer.py`) ajustado e 100% da suíte unitária passando.
- [ ] Cálculo de Ratings (`A` a `E`) para Reliability, Security e Maintainability validado.
- [ ] Quality Profiles e Quality Gates ("POLARIS Way") operacionais no Server e Scanner CLI (`--fail-on-quality-gate` retornando `exit_code = 3`).
- [ ] Evidência formal registrada em `vault/09-Validation/Reports/VAL-GOAL-007-FINAL.md` e indexada em `vault/09-Validation/Index.md`.
- [ ] `Current-State.md` atualizado para a versão `0.3.0`.
