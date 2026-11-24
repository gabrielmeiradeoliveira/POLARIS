---
id: ADR-001
title: Nova implementação independente do projeto anterior
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - adr
---

# ADR-001: Nova implementação independente do projeto anterior

- **Identificador:** ADR-001
- **Estado:** ACCEPTED
- **Data:** 2026-11-14

## Contexto
O projeto POLARIS está iniciando uma nova fase (2.0) com foco em governança, determinismo, segurança e paridade funcional com o SonarQube.

## Problema
Decidir se o novo repositório deve reaproveitar ou importar código da implementação anterior do POLARIS.

## Alternativas Consideradas
1. Importar e refatorar o código do POLARIS anterior.
2. Iniciar uma nova implementação independente do zero.

## Decisão
Iniciar uma nova implementação completamente independente da arquitetura anterior, sem importação automática de código legado.

## Justificativa
Evitar débitos técnicos ocultos, acoplamentos legados e suposições arquiteturais não documentadas.

## Consequências
- **Positivas:** Fundação limpa, rastreável e aderente às novas políticas de qualidade e segurança.
- **Negativas / Riscos:** Todo o código do produto precisará ser especificado e construído do zero.
