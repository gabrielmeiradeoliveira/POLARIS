---
id: DOC-048
title: Modelo de Domínio e Ciclos de Vida
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - domain-model
---

# Modelo de Domínio e Ciclos de Vida

## 1. Entidades Principais (Candidatas)

- **Estrutura:** `Project`, `Repository`, `Branch`, `PullRequest`, `SourceFile`.
- **Análise:** `Analysis`, `AnalysisTask`, `Analyzer`, `CoverageReport`, `DuplicationBlock`.
- **Regras e Issues:** `Rule`, `RuleParameter`, `Issue`, `IssueLocation`, `IssueHistory`.
- **Qualidade e Métricas:** `Metric`, `Measure`, `QualityProfile`, `ActiveRule`, `QualityGate`, `GateCondition`, `GateEvaluation`.
- **Governança:** `User`, `Permission`, `AuditEvent`.

## 2. Ciclo de Vida e Fingerprinting de Issues

- **Identidade Estável:** Issues **não** são identificadas apenas pelo número da linha. O fingerprinting combina `ruleId`, caminho relativo normalizado, hash estrutural/AST do trecho afetado e contexto de escopo (função/classe).
- **Rastreamento:** Na nova análise, issues são comparadas com o snapshot anterior da branch/baseline para detectar novas issues, reconhecer existentes (mesmo após movimentação de linhas ou renomeação), marcar resolvidas e preservar `IssueHistory` (incluindo falsos positivos e decisões humanas).

## 3. Motor de Regras, Quality Profiles e Quality Gates

- **Regras:** Separação estrita entre metadados (ID estável, linguagem, categoria, severidade, justificativa, exemplos conformes/não conformes), implementação e ativação por perfil.
- **Quality Profiles:** Conjunto versionado de regras ativas e parâmetros por linguagem/projeto.
- **Quality Gates:** Avaliação determinística de condições sobre métricas de Código Novo e Código Geral. **Regra de segurança:** Se métricas obrigatórias estiverem ausentes ou a análise for incompleta, o Quality Gate **não** é aprovado automaticamente (retorna `ERROR`/`FAILED` ou `INCOMPLETE`).
