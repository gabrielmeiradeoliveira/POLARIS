---
id: ADR-007
title: POLARIS Server como Monólito Modular
status: active
version: 1
created: 2026-11-14
updated: 2026-11-17
owner: architecture
tags:
  - polaris
  - adr
---

# ADR-007: POLARIS Server como Monólito Modular

- **Identificador:** ADR-007
- **Estado:** ACCEPTED (Aprovado pelo responsável em 2026-11-14)
- **Data:** 2026-11-14

## Contexto
O POLARIS 2.x opera localmente e em instalações self-hosted simples, sem necessidade de infraestrutura distribuída.

## Problema
Escolher entre monólito tradicional, monólito modular ou microsserviços.

## Alternativas Consideradas
1. Microsserviços distribuídos.
2. Monólito tradicional sem limites internos.
3. Monólito modular com limites rígidos entre os 18 módulos de domínio.

## Decisão
Adotar **Monólito Modular** como arquitetura inicial do POLARIS Server.

## Justificativa
Evita complexidade de rede/orquestração, facilita testes de integração locais e preserva modularidade para evolução futura.

## Consequências
- **Positivas:** Implantação única, transações ACID locais e baixo custo operacional.
- **Negativas / Riscos:** Exige disciplina arquitetural para evitar acoplamento indevido entre módulos.
