---
id: ADR-011
title: Persistência Relacional como Candidata Inicial
status: active
version: 1
created: 2026-11-14
updated: 2026-11-17
owner: architecture
tags:
  - polaris
  - adr
---

# ADR-011: Persistência Relacional como Candidata Inicial

- **Identificador:** ADR-011
- **Estado:** ACCEPTED (Aprovado pelo responsável em 2026-11-14)
- **Data:** 2026-11-14

## Contexto
O POLARIS Server precisa armazenar projetos, análises, issues, histórico, métricas e auditoria com integridade transacional.

## Problema
Definir o paradigma de persistência inicial sem escolher ainda o SGBD específico.

## Alternativas Consideradas
1. Banco orientado a documentos ou arquivos JSON soltos.
2. Armazenamento relacional com integridade transacional (ACID).

## Decisão
Adotar armazenamento relacional com **PostgreSQL 17** (`psycopg` 3), conforme validado no `GOAL-003`.

## Justificativa
Garante integridade referencial, consultas estruturadas de métricas/issues e atomicidade na ingestão de análises.

## Consequências
- **Positivas:** Consistência forte e facilidade de auditoria.
- **Negativas / Riscos:** Exige migrações versionadas de esquema.
