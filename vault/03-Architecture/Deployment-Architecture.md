---
id: DOC-052
title: Arquitetura Operacional e de Implantação
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - deployment
---

# Arquitetura Operacional e de Implantação

## Cenários Suportados (Sem Infraestrutura Distribuída)

1. **Desenvolvimento Local:** Execução direta do servidor e scanner na estação de trabalho.
2. **Instalação Local Individual:** Pacote único ou container local com persistência em volume local.
3. **Servidor Self-Hosted:** Instância única em rede interna da equipe.
4. **Integração CI/CD:** Scanner executado no runner de CI comunicando-se com o servidor local/self-hosted ou operando em modo independente.

## Requisitos Operacionais

- Health check explícito (`/api/v1/health`) verificando servidor e persistência.
- Logs estruturados sem exposição de segredos.
- Encerramento seguro (graceful shutdown) aguardando conclusão de transações ativas.
- Operação 100% funcional sem internet, APIs externas ou serviços de IA.
