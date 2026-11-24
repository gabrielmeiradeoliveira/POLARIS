---
id: DOC-051
title: Arquitetura de API e Dashboard
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - api
---

# Arquitetura de API e Dashboard

## 1. API HTTP Local (Conceitual)

- **Versionamento:** Prefixo explícito (ex.: `/api/v1/...`).
- **Segurança:** Autenticação via sessão/token Bearer, autorização RBAC por recurso/projeto, validação estrita de entrada e rate limiting básico.
- **Padrões:** Paginação determinística, filtros por projeto/branch/severidade e formato de erro padronizado (sem stack traces internos).
- **Recursos Principais:** `/projects`, `/analyses`, `/issues`, `/measures`, `/rules`, `/quality-profiles`, `/quality-gates`, `/users`, `/health`.

## 2. Dashboard Web (Responsabilidades)

Interface web local (sem escolha de framework frontend neste GOAL) responsável por:
- Visão geral de projetos e status de Quality Gates.
- Navegação por métricas (Código Novo vs Código Geral) e histórico.
- Triagem de issues com contexto de arquivo/linha.
- Gestão de Quality Profiles, Quality Gates e Administração local.
