---
id: ADR-003
title: Escopo restrito às quatro linguagens
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - adr
  - languages
---

# ADR-003: Escopo restrito às quatro linguagens

- **Identificador:** ADR-003
- **Estado:** ACCEPTED
- **Data:** 2026-11-14

## Contexto
Suportar muitas linguagens simultaneamente dilui esforços e compromete a profundidade da análise estática.

## Problema
Definir o conjunto oficial de linguagens suportadas pelo POLARIS 2.0.

## Alternativas Consideradas
1. Suporte amplo a dezenas de linguagens desde o início.
2. Restringir o escopo oficial a quatro linguagens prioritárias.

## Decisão
Restringir o escopo oficial do POLARIS 2.0 a **Python**, **C# / .NET**, **Java** e **SQL**.

## Justificativa
Permite focar qualidade, precisão dos analisadores e cobertura de testes nas linguagens prioritárias.

## Consequências
- **Positivas:** Escopo controlado e maior profundidade técnica por linguagem.
- **Negativas / Riscos:** Outras linguagens ficam fora do escopo até nova decisão formal.
