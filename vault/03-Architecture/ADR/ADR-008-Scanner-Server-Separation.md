---
id: ADR-008
title: Separação entre POLARIS Scanner e POLARIS Server
status: active
version: 1
created: 2026-11-14
updated: 2026-11-17
owner: architecture
tags:
  - polaris
  - adr
---

# ADR-008: Separação entre POLARIS Scanner e POLARIS Server

- **Identificador:** ADR-008
- **Estado:** ACCEPTED (Aprovado pelo responsável em 2026-11-14)
- **Data:** 2026-11-14

## Contexto
O usuário precisa executar análises tanto localmente quanto em pipelines CI/CD, comunicando-se com o servidor ou gerando relatórios locais.

## Problema
Definir se a análise de arquivos ocorre dentro do servidor ou em um cliente CLI dedicado.

## Alternativas Consideradas
1. Servidor acessando diretamente o sistema de arquivos do repositório.
2. Scanner CLI separado comunicando-se via contrato versionado.

## Decisão
Separar `POLARIS Scanner` (CLI) do `POLARIS Server`, suportando modo local independente e modo integrado.

## Justificativa
Permite execução em CI/CD sem expor o repositório ao servidor e isola a leitura de código não confiável.

## Consequências
- **Positivas:** Portabilidade para CI/CD e menor superfície de ataque no servidor.
- **Negativas / Riscos:** Exige manutenção de contrato versionado entre Scanner e Server.
