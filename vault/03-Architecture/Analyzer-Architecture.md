---
id: DOC-046
title: Arquitetura dos Analisadores Especializados
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - analyzers
---

# Arquitetura dos Analisadores Especializados

## 1. Autonomia por Ecossistema

Cada analisador (**Python**, **C# / .NET**, **Java**, **SQL**) tem autonomia para usar as técnicas mais adequadas ao seu ecossistema (parsing, AST, resolução de símbolos/tipos, fluxo de controle/dados, taint analysis, detecção de duplicação e métricas), sem obrigar uma representação intermediária única. A complexidade é proporcional à necessidade de cada regra.

## 2. Contrato Comum de Integração

Todo analisador expõe:
- Identificação, versão e linguagens suportadas.
- Capacidades declaradas e catálogo de regras disponíveis.
- Entrada: lista de arquivos, configuração e regras ativas.
- Saída: issues, métricas, duplicações, diagnósticos, erros e limitações.

## 3. Estados Explícitos de Análise por Arquivo

Uma falha de análise **nunca** deve ser interpretada como ausência de problemas:
- `ANALYZED_SUCCESS`: Arquivo analisado integralmente.
- `ANALYZED_PARTIAL`: Arquivo parcialmente analisado (com diagnósticos).
- `UNSUPPORTED_FILE`: Arquivo fora do escopo/linguagem suportada.
- `PARSE_ERROR`: Erro sintático impediu análise completa.
- `SEMANTIC_ERROR`: Erro na resolução de símbolos/tipos.
- `ANALYZER_FAILURE`: Falha interna ou timeout do analisador.
