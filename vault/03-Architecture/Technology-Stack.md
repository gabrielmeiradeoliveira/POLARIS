---
id: DOC-012
title: Stack Tecnológica
status: active
version: 3
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - tech-stack
---

# Stack Tecnológica Recomendada (Validada no GOAL-003-R3)

> [!NOTE]
> Esta stack foi validada experimentalmente nos `GOAL-003-R2` e `GOAL-003-R3` e permanece como proposta (`PROPOSED`) aguardando aprovação humana para o `GOAL-004`.

| Camada | Tecnologia Recomendada | Versão / Referência | Licença |
| :--- | :--- | :--- | :--- |
| **Backend / API** | Python + FastAPI + Uvicorn + Pydantic | `3.12+` / `0.115.6` / `0.34.0` | PSF / MIT |
| **Scanner** | Python CLI (invocação isolada via subprocess) | `3.12+` | PSF |
| **Analisador Python** | AST nativo + LibCST + Astroid | `1.5.0` / `3.3.5` | PSF / MIT / LGPL-2.1 |
| **Analisador C# / .NET** | Microsoft Roslyn (`Microsoft.CodeAnalysis.CSharp`) | `4.11.0` (`.NET 8/11`) | MIT |
| **Analisador Java** | JavaParser Symbol Solver (build Maven) | `3.26.2` (JDK 21) | Apache-2.0 / LGPL-3.0 |
| **Analisador SQL** | SQLGlot | `25.32.1` | MIT |
| **Banco de Dados** | PostgreSQL (`psycopg` 3) | `17` (`psycopg 3.2.3`) | PostgreSQL / LGPL-3.0 |
| **Frontend** | React + TypeScript + Vite | `18.3.1` / `5.6.3` / `6.0.1` | MIT |
| **Testes** | `unittest` / `pytest` + `tsc` + `dotnet test` + JUnit | N/A | N/A |
| **Infraestrutura Local** | Docker & Docker Compose (PostgreSQL / Maven build) | Docker `29.6.1` | Apache-2.0 |
