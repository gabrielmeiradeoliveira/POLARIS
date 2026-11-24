---
id: ADR-006
title: Validação baseada em evidências
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - adr
  - validation
---

# ADR-006: Validação baseada em evidências

- **Identificador:** ADR-006
- **Estado:** ACCEPTED
- **Data:** 2026-11-14

## Contexto
Declarações de conclusão baseadas apenas em compilação ou opinião de agente geram falsos positivos de qualidade.

## Problema
Estabelecer um critério rigoroso para considerar uma funcionalidade concluída.

## Alternativas Consideradas
1. Aceitar conclusão com base em testes unitários isolados ou revisão visual.
2. Exigir validação real com evidências registradas e estados explícitos (`IMPLEMENTED` vs `VALIDATED`).

## Decisão
Adotar validação baseada em evidências reais como regra obrigatória. `IMPLEMENTED` não significa `VALIDATED`. Toda validação deve registrar ambiente, comandos, resultados observados, testes e limitações sem fabricação de dados.

## Justificativa
Garante confiabilidade real do produto e rastreabilidade completa das entregas.

## Consequências
- **Positivas:** Alta confiabilidade nas entregas e redução de regressões.
- **Negativas / Riscos:** Maior rigor e tempo dedicado à coleta de evidências.
