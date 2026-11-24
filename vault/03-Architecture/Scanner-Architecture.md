---
id: DOC-045
title: Arquitetura do POLARIS Scanner
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - scanner
---

# Arquitetura do POLARIS Scanner

## 1. Responsabilidades

- Identificar o projeto (`projectKey`) e metadados Git (branch, commit).
- Carregar configurações locais e aplicar inclusões/exclusões determinísticas.
- Descobrir arquivos e identificar linguagens suportadas (Python, C#, Java, SQL).
- Carregar Quality Profiles ativos (do servidor ou configuração local).
- Selecionar e invocar analisadores especializados de forma isolada.
- Importar relatórios externos de cobertura de testes.
- Consolidar resultados em contrato versionado (`Analysis-Contract.md`).
- Enviar resultados ao POLARIS Server ou gravar relatório local.
- Informar erros, estados parciais e retornar códigos de saída padronizados para CI/CD.

## 2. Modos de Execução Compartilhados

- **Modo Local Independente:** Executa análise e gera relatório local sem depender de servidor ativo.
- **Modo Integrado ao POLARIS Server:** Obtém perfis/configurações do servidor, envia relatório e consulta status do Quality Gate.
- Ambos compartilham o mesmo núcleo de descoberta, escopo e invocação de analisadores, variando apenas o adaptador de entrada de configuração e saída de resultados.
