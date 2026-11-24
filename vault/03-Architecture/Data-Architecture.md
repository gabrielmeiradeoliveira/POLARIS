---
id: DOC-050
title: Arquitetura de Dados e Persistência
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - data
---

# Arquitetura de Dados e Persistência

## 1. Modelo Candidato

Armazenamento **relacional** como candidato inicial (sem escolha definitiva de SGBD neste GOAL), garantindo:
- **Integridade Transacional (ACID):** Ingestão de uma análise ocorre de forma atômica; falhas não corrompem snapshots anteriores.
- **Isolamento por Projeto:** Todas as consultas de issues, métricas e histórico filtram obrigatoriamente por `projectId`.
- **Não Armazenamento de Código Integral:** Evitar armazenar o código-fonte completo dos repositórios analisados sem necessidade funcional documentada; armazenar apenas metadados, localizações e trechos mínimos necessários para exibição de contexto.
- **Retenção, Backup e Migrações:** Políticas configuráveis de retenção de snapshots antigos, backup consistente do banco local e migrações versionadas.
