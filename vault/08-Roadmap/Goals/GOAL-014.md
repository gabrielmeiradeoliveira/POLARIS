---
id: GOAL-014
title: Issue Relocation Difuso e Consciência Semântica de Frameworks
status: PLANNED
priority: HIGH
depends_on:
  - GOAL-012
  - GOAL-013
version_target: 2.3.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - release-2.3.0
  - issue-relocation
  - framework-awareness
  - false-positive-reduction
  - sonarqube-parity
---

# GOAL-014 — Issue Relocation Difuso e Consciência Semântica de Frameworks (`2.3.0`)

## 1. Objetivo
Eliminar os dois maiores causadores de ruído em projetos reais de engenharia de software:
1. **Falsas "Issues Novas" após refatoração:** Motor de **Issue Relocation em 4 estágios** (`src/polaris_server/relocation.py`) acompanhando issues existentes mesmo quando linhas são movidas, funções extraídas ou arquivos renomeados via `git mv`.
2. **Falsos Positivos de Framework:** Consciência semântica de frameworks (*FastAPI/SQLAlchemy*, *ASP.NET Core/EF Core*, *Spring Boot/JPA*), reconhecendo pontos de entrada, injeção de dependência e contratos de ciclo de vida.

## 2. Critérios de Aceitação
- [ ] Motor de Issue Relocation em 4 estágios validado com preservação de `FALSE_POSITIVE` / `ACCEPTED` após movimentação de linhas e renomeação de arquivos.
- [ ] Suíte de testes de framework (`FastAPI`, `ASP.NET Core`, `Spring Boot`) garantindo zero falsos positivos em controllers, DTOs e DI.
- [ ] Evidência registrada em `vault/09-Validation/Reports/VAL-GOAL-014-RELEASE-2.3.0.md` e `Current-State.md` atualizado para `2.3.0`.
