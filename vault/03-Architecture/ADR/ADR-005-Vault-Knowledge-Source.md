---
id: ADR-005
title: Vault como fonte oficial de conhecimento
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - adr
  - vault
---

# ADR-005: Vault como fonte oficial de conhecimento

- **Identificador:** ADR-005
- **Estado:** ACCEPTED
- **Data:** 2026-11-14

## Contexto
Agentes de desenvolvimento operam em sessões distintas e não devem depender apenas do histórico de conversa.

## Problema
Garantir memória operacional permanente, rastreável e acessível a qualquer agente ou humano.

## Alternativas Consideradas
1. Documentação dispersa em READMEs ou dependente de histórico de chat.
2. Centralizar o conhecimento oficial em `vault/` com Markdown compatível com Obsidian.

## Decisão
Adotar `vault/` como fonte oficial de conhecimento e memória operacional permanente do POLARIS, utilizando Markdown compatível com Obsidian sem depender de plugins exclusivos.

## Justificativa
Assegura continuidade entre sessões, rastreabilidade de decisões e leitura obrigatória antes de qualquer tarefa.

## Consequências
- **Positivas:** Continuidade operacional e sincronização entre documentação e código.
- **Negativas / Riscos:** Exige disciplina de atualização documental ao fim de cada tarefa.
