---
id: DOC-049
title: Arquitetura de Componentes do POLARIS Server
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - components
---

# Arquitetura de Componentes — POLARIS Server (Monólito Modular)

Os 18 módulos residem no mesmo processo do POLARIS Server, comunicando-se via interfaces internas explícitas, sem dependências circulares nem acesso direto às tabelas de outro módulo.

| Módulo | Responsabilidade Principal | Entidades Principais | Requisitos |
| :--- | :--- | :--- | :--- |
| `Projects` | Ciclo de vida e isolamento de projetos | `Project`, `Repository` | `REQ-FUNC-001` |
| `Analyses` | Ingestão de relatórios e coordenação | `Analysis`, `SourceFile` | `REQ-FUNC-002`, `013` |
| `Issues` | Fingerprinting, triagem e histórico | `Issue`, `IssueHistory` | `REQ-FUNC-005` |
| `Rules` | Catálogo versionado de regras | `Rule`, `RuleParameter` | `REQ-FUNC-004` |
| `Measures` | Cálculo, agregação e fórmulas de métricas | `Metric`, `Measure` | `REQ-FUNC-006`, `007`, `010` |
| `QualityProfiles` | Perfis ativos por linguagem/projeto | `QualityProfile`, `ActiveRule` | `REQ-FUNC-012` |
| `QualityGates` | Avaliação Pass/Fail sobre limiares | `QualityGate`, `GateEvaluation` | `REQ-FUNC-011` |
| `NewCode` | Isolamento de delta (Clean as You Code) | `Analysis` (baseline) | `REQ-FUNC-014` |
| `Branches` | Rastreamento independente por branch | `Branch` | `REQ-FUNC-015` |
| `PullRequests` | Análise delta de PRs | `PullRequest` | `REQ-FUNC-016` |
| `Coverage` | Ingestão e agregação de cobertura | `CoverageReport` | `REQ-FUNC-009` |
| `Duplications` | Armazenamento de blocos duplicados | `DuplicationBlock` | `REQ-FUNC-008` |
| `Users` | Identidade local e tokens de acesso | `User` | `REQ-FUNC-019` |
| `Permissions` | Controle de acesso (RBAC) | `Permission` | `REQ-FUNC-019` |
| `Administration` | Configurações globais da instância | Configurações | `REQ-FUNC-018` |
| `BackgroundTasks` | Fila local assíncrona de processamento | `AnalysisTask` | `REQ-NFR-001`, `013` |
| `Audit` | Registro imutável de eventos sensíveis | `AuditEvent` | `REQ-NFR-009` |
| `API` | Exposição HTTP versionada e validação | DTOs / Contratos | `REQ-FUNC-020`, `017` |

- **Dependências Proibidas:** Módulos de domínio (`Issues`, `Measures`, `QualityGates`) não podem depender da camada `API`; nenhum módulo pode importar SDKs de IA.
- **Preservação de Limites:** Regras de arquitetura automatizadas (fitness functions) e interfaces explícitas por módulo.
