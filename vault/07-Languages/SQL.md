---
id: DOC-030
title: Linguagem Suportada — SQL
status: active
version: 2
created: 2026-11-14
updated: 2026-11-14
owner: product
tags:
  - polaris
  - languages
  - sql
---

# SQL

SQL é uma das quatro linguagens oficialmente suportadas pelo POLARIS 2.0 ([ADR-003](../03-Architecture/ADR/ADR-003-Supported-Languages.md)).

## Ecossistema e Dialetos Relevantes (Referência)
- **Arquivos-fonte:** `.sql`
- **Dialetos comuns:** ANSI SQL, PostgreSQL, T-SQL (SQL Server), PL/SQL (Oracle), MySQL

## Propostas Pendentes de Decisão
- Quais dialetos SQL serão suportados na V2.0 inicial.
- Estratégia de parsing multi-dialeto determinístico.
- Conjunto inicial de regras de paridade com SonarQube.
