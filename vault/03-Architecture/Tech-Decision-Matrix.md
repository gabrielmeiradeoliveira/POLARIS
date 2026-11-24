---
id: DOC-057
title: Matriz de Decisão Tecnológica
status: active
version: 2
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - tech-decision
---

# Matriz de Decisão Tecnológica — GOAL-003-R3

| Categoria | Candidato Selecionado | Tipo de Evidência | Justificativa Principal |
| :--- | :--- | :--- | :--- |
| **Backend** | Python + FastAPI + Pydantic | `EXPERIMENTAL` | Validação automática de contrato, baixo overhead, integração direta com PostgreSQL (`psycopg 3`) e Python/SQL analyzers. |
| **Scanner** | Python CLI | `EXPERIMENTAL` | Portável (Windows/Linux), controle de timeout/subprocesso, path canonicalization e invocação dos 4 analisadores. |
| **Analisador Python** | AST + LibCST + Astroid | `EXPERIMENTAL` | `Precision=1.0, Recall=1.0, F1=1.0` no corpus experimental, incluindo inferência semântica. |
| **Analisador C#** | Microsoft Roslyn `4.11.0` | `EXPERIMENTAL` | Parser oficial da Microsoft com `SemanticModel` real (`Precision=1.0, Recall=1.0, F1=1.0`). |
| **Analisador Java** | JavaParser Symbol Solver `3.26.2` | `EXPERIMENTAL` | Resolução de símbolos/tipos leve via Maven/JDK 21 sem exigir IDE Eclipse completa (`Precision=1.0, Recall=1.0, F1=1.0`). |
| **Analisador SQL** | SQLGlot `25.32.1` | `EXPERIMENTAL` | Multi-dialeto nativo (PostgreSQL, T-SQL, MySQL, etc.) em Python (`Precision=1.0, Recall=1.0, F1=1.0`). |
| **Persistência** | PostgreSQL `17` | `EXPERIMENTAL` | Transações ACID, `ROLLBACK`, `ON DELETE CASCADE` e isolamento por `project_key` validados. |
| **Frontend** | React + TypeScript + Vite | `EXPERIMENTAL` | Tipagem estática (`tsc -b`) e build limpo (`144.76 kB` bundle) consumindo API real. |
