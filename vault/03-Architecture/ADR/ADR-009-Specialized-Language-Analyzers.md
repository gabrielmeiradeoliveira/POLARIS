---
id: ADR-009
title: Analisadores Especializados por Linguagem
status: active
version: 1
created: 2026-11-14
updated: 2026-11-17
owner: architecture
tags:
  - polaris
  - adr
---

# ADR-009: Analisadores Especializados por Linguagem

- **Identificador:** ADR-009
- **Estado:** ACCEPTED (Aprovado pelo responsável em 2026-11-14)
- **Data:** 2026-11-14

## Contexto
Python, C# / .NET, Java e SQL possuem ecossistemas, gramáticas e necessidades semânticas distintas.

## Problema
Decidir se todos os analisadores devem compartilhar uma única representação intermediária (IR) obrigatória.

## Alternativas Consideradas
1. Impor uma IR única universal para todas as linguagens.
2. Dar autonomia a cada analisador, integrando-os via contrato comum de entrada/saída.

## Decisão
Adotar analisadores especializados por ecossistema com autonomia técnica e contrato comum de integração.

## Justificativa
Evita abstrações prematuras e permite usar as melhores técnicas de parsing/análise de cada linguagem.

## Consequências
- **Positivas:** Maior precisão e menor acoplamento entre linguagens.
- **Negativas / Riscos:** Regras transversais (ex.: duplicação) precisam de implementação ou normalização por linguagem.
