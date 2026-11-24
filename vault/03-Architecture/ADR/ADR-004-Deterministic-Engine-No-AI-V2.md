---
id: ADR-004
title: Motor determinístico sem IA na versão 2.x
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - adr
  - deterministic
---

# ADR-004: Motor determinístico sem IA na versão 2.x

- **Identificador:** ADR-004
- **Estado:** ACCEPTED
- **Data:** 2026-11-14

## Contexto
A análise estática precisa ser previsível, auditável e capaz de operar integralmente em ambiente local.

## Problema
Definir se a versão 2.x do POLARIS incluirá recursos de inteligência artificial no produto.

## Alternativas Consideradas
1. Integrar LLMs ou serviços de IA já na versão 2.x.
2. Manter a versão 2.x integralmente local e determinística, postergando IA para a versão 3.0.

## Decisão
A versão 2.x do POLARIS será integralmente local e determinística. É proibido adicionar SDKs de LLMs, serviços de inferência ou APIs de IA ao produto na versão 2.x. A integração de IA será considerada exclusivamente na versão 3.0.

## Justificativa
Garante reprodutibilidade, previsibilidade, privacidade local e menor complexidade operacional na V2.x.

## Consequências
- **Positivas:** Resultados determinísticos e zero dependência de provedores externos de IA.
- **Negativas / Riscos:** Recursos baseados em IA ficam adiados para a V3.0.
