---
id: FUNCTIONAL-PARITY
title: Matriz de Paridade Funcional — POLARIS 2.0 vs SonarQube
type: validation-report
status: COMPLETED
created_at: 2026-11-15
updated_at: 2026-11-15
tags: [parity, sonarqube, goal-019]
---

# Matriz de Paridade Funcional — POLARIS 2.0

| Funcionalidade | Referência SonarQube | Edição | Estado | Evidência | Limitação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Scanner CLI (`analyze`) | SonarScanner | Community | `SUPPORTED` | `test_analyze_command.py` | Análise local/conectada |
| Analisadores (Python, C#, Java, SQL) | Language Analyzers | Community | `PARTIALLY_SUPPORTED` | `tests/unit/analyzers/` | 8 regras executáveis no catálogo base |
| Gestão de Issues e Hotspots | Issues / Security Hotspots | Community | `SUPPORTED` | `test_governance_api.py` | Persistência em memória nos serviços novos |
| Quality Profiles & Gates | Quality Profiles / Gates | Community | `SUPPORTED` | `test_goal019_maturity.py` | — |
| Cobertura & Duplicação | Coverage / CPD | Community | `SUPPORTED` | `test_advanced_analysis.py` | Cobertura XML + tokens |
| New Code, Branches & PRs | Branch / PR Analysis | Developer | `PARTIALLY_SUPPORTED` | `git_new_code.py`, `git_branch_service.py` | Sem decoração remota automática |
| Auth, Tokens & RBAC | Administration / Security | Community | `SUPPORTED` | `test_security_cicd.py` | — |
| Recursos de IA / Cloud | AI CodeFix / SonarCloud | Commercial | `OUT_OF_SCOPE` | `AGENTS.md` | Reservado ao POLARIS 3.0 |
