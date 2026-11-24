---
id: DOC-027
title: Linguagem Suportada — Python
status: active
version: 2
created: 2026-11-14
updated: 2026-11-14
owner: product
tags:
  - polaris
  - languages
  - python
---

# Python

Python é uma das quatro linguagens oficialmente suportadas pelo POLARIS 2.0 ([ADR-003](../03-Architecture/ADR/ADR-003-Supported-Languages.md)).

## Ecossistema e Formatos de Projeto (Referência)
- **Arquivos-fonte:** `.py`, `.pyi`
- **Descritores de projeto comuns:** `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt`
- **Relatórios de cobertura comuns:** `coverage.xml` (Cobertura XML), LCOV

## Propostas Pendentes de Decisão
- Versões de Python suportadas (ex.: Python 3.10+ vs 3.8+).
- Estratégia de parsing estático (AST nativo ou parser dedicado) sem execução de código.
- Conjunto inicial de regras de paridade com SonarQube.
