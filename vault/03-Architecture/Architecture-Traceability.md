---
id: DOC-056
title: Rastreabilidade Arquitetural
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - traceability
---

# Rastreabilidade Arquitetural

| Origem | Cobertura Arquitetural | Documento Principal |
| :--- | :--- | :--- |
| `REQ-FUNC-001`, `018`, `019` | Módulos `Projects`, `Administration`, `Users`, `Permissions` | `Component-Architecture.md` |
| `REQ-FUNC-002`, `003`, `021` | `POLARIS Scanner` (modos local e integrado) | `Scanner-Architecture.md` |
| `REQ-FUNC-004`, `005`, `006`, `007`, `008`, `009`, `010` | Analisadores + `Rules`, `Issues`, `Measures`, `Coverage`, `Duplications` | `Analyzer-Architecture.md`, `Domain-Model.md` |
| `REQ-FUNC-011`, `012`, `013`, `014`, `015`, `016` | `QualityProfiles`, `QualityGates`, `NewCode`, `Branches`, `PullRequests` | `Component-Architecture.md`, `Domain-Model.md` |
| `REQ-FUNC-017`, `020`, `022` | `API`, `Dashboard Web`, `Deployment` | `API-Architecture.md`, `Deployment-Architecture.md` |
| `REQ-NFR-001` a `REQ-NFR-013` | Monólito Modular, ACID, Threat Model, Testes de Performance/Segurança | `Security-Architecture.md`, `Threat-Model.md`, `Testing-Architecture.md` |
| `UJ-001` a `UJ-012` | Fluxo completo Scanner -> API -> Server -> Persistência -> Dashboard | `Container-Architecture.md`, `API-Architecture.md` |
