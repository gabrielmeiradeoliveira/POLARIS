---
id: DOC-055
title: Arquitetura de Testes
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: qa
tags:
  - polaris
  - architecture
  - testing
---

# Arquitetura de Testes

## 1. Pirâmide e Camadas de Teste

- **Unitários:** Lógica de domínio, cálculos de métricas, Quality Gates e regras isoladas.
- **Integração:** Persistência real, módulos do Server e comunicação Scanner <-> Server.
- **Contrato:** Validação de esquema do `Analysis-Contract.md` e endpoints da API.
- **End-to-End (E2E):** Jornadas `UJ-001` a `UJ-012` em ambiente real.
- **Regressão, Segurança, Desempenho, Recuperação e Instalação:** Conforme `Testing-Strategy.md`.

## 2. Estratégia Específica para Analisadores

- **Conjuntos:** Casos positivos, negativos, limítrofes, golden tests, corpus de regressão, fuzzing de parsers, testes de determinismo e compatibilidade por versão de linguagem.
- **Métricas de Avaliação:** Precisão, Recall, F1-score, taxa de falsos positivos/negativos, cobertura de regras, tempo de análise e pico de memória.
- **Independência de Corpus:** Separar estritamente o conjunto de desenvolvimento do conjunto reservado para avaliação final; usar SonarQube como referência comparativa, não como fonte exclusiva de verdade.
