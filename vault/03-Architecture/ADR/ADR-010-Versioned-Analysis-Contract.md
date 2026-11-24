---
id: ADR-010
title: Contrato Versionado de Resultados de Análise
status: active
version: 1
created: 2026-11-14
updated: 2026-11-17
owner: architecture
tags:
  - polaris
  - adr
---

# ADR-010: Contrato Versionado de Resultados de Análise

- **Identificador:** ADR-010
- **Estado:** ACCEPTED (Aprovado pelo responsável em 2026-11-14)
- **Data:** 2026-11-14

## Contexto
Analisadores, Scanner e Server precisam trocar issues, métricas, cobertura, duplicações e estados de erro.

## Problema
Definir o formato de intercâmbio entre componentes.

## Alternativas Consideradas
1. Usar exclusivamente SARIF puro.
2. Definir contrato versionado próprio do POLARIS, conceitualmente compatível com SARIF para issues.

## Decisão
Adotar contrato versionado próprio (`Analysis-Contract.md`, schema v1 em JSON/Pydantic) com compatibilidade conceitual com SARIF.

Campos obrigatórios do payload v1 de análise:
- `contract_version` (string, ex.: `"1.0"`)
- `project_key` (string)
- `analysis_id` (UUID/string)
- `timestamp` (ISO 8601)
- `branch` (string)
- `files` (lista de arquivos analisados com `path`, `language`, `status`, `metrics`)
- `issues` (lista de issues com `rule_id`, `severity`, `type`, `file_path`, `line`, `message`)
- `metrics` (agregados do projeto)
- `errors` (lista de falhas parciais por arquivo/analisador, se houver)

## Justificativa
SARIF não cobre nativamente todas as métricas, estados por arquivo e necessidades de persistência do POLARIS.

## Consequências
- **Positivas:** Contrato explícito, validável e evolutivo.
- **Negativas / Riscos:** Requer exportador dedicado caso se deseje emitir SARIF puro no futuro.
