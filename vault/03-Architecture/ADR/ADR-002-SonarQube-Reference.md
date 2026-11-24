---
id: ADR-002
title: SonarQube como referência funcional
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - adr
  - sonarqube
---

# ADR-002: SonarQube como referência funcional

- **Identificador:** ADR-002
- **Estado:** ACCEPTED
- **Data:** 2026-11-14

## Contexto
O POLARIS 2.0 precisa de uma referência clara e consolidada de capacidades para análise estática de código.

## Problema
Definir o modelo funcional de referência para orientar a especificação do produto.

## Alternativas Consideradas
1. Definir um conjunto próprio de conceitos sem referência de mercado.
2. Adotar o SonarQube como referência de paridade funcional.

## Decisão
Adotar o SonarQube como referência de paridade funcional para estudo e especificação do POLARIS 2.0, sem copiar código proprietário, marcas ou materiais protegidos.

## Justificativa
Fornece vocabulário e modelo funcional amplamente reconhecidos (scanner, issues, métricas, quality gates, quality profiles, etc.).

## Consequências
- **Positivas:** Alinhamento claro de escopo e requisitos.
- **Negativas / Riscos:** Exige estudo formal da documentação oficial do SonarQube no `GOAL-001`.
