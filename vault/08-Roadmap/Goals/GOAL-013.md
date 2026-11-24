---
id: GOAL-013
title: Motor de Grafos Semânticos (CFG, Call Graph e Taint Analysis Inter-Procedural)
status: COMPLETED
priority: HIGH
depends_on:
  - GOAL-006
  - GOAL-012
version_target: 2.2.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - release-2.2.0
  - cfg
  - call-graph
  - taint-analysis
  - symbolic-execution
  - sonarqube-parity
---

# GOAL-013 — Motor de Grafos Semânticos (CFG, Call Graph e Taint Analysis Inter-Procedural) (`2.2.0`)

## 1. Objetivo
Elevar a profundidade de análise estática do **POLARIS 2.x** além da inspeção puramente sintática (AST), implementando **Control Flow Graphs (CFG)**, **Call Graphs** e **Taint Analysis Inter-Procedural baseado em Function Summaries** nos workers de **Python**, **C# / .NET** e **Java** (`ADR-009`), emitindo trilhas completas de propagação de dados (`taint_flow`) no **Contrato de Análise v1** (`ADR-010`) e reduzindo falsos positivos em análises multi-camada (*Controller → Service → Repository*).

## 2. Critérios de Aceitação
- [ ] CFG intra-procedural, Call Graph inter-procedural e Taint Analysis com *Function Summaries* operacionais em **Python**, **C# (Roslyn)** e **Java (JavaParser Symbol Solver)**.
- [ ] Regras baseadas em grafo (`G3649`, `G2076`, `G2083`, `G2259`, `G2095`/`G2583`/`G1764`) validadas com cenários cross-file (3 camadas) e sanitização parcial/total.
- [ ] Trilhas `taint_flow` multi-arquivo renderizadas corretamente no Split-Pane da interface web (`web/`).
- [ ] Benchmarks de latência registrados dentro das metas.
- [ ] Evidência formal registrada em `vault/09-Validation/Reports/VAL-GOAL-013-RELEASE-2.2.0.md` e indexada em `vault/09-Validation/Index.md`.
- [ ] `Current-State.md` atualizado para a versão `2.2.0`.
