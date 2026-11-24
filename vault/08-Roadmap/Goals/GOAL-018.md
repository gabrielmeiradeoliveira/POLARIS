---
id: GOAL-018
title: Engenharia de Performance Real, Cache JSON.GZ, Segurança para Monolitos e Modo Dev
status: IN_PROGRESS
priority: HIGH
depends_on:
  - GOAL-017
version_target: 2.6.1
created: 2026-11-24
updated: 2026-11-24
owner: project
tags:
  - goal
  - release-2.6.1
  - performance
  - cache-json-gz
  - monolith-safety
  - changed-only
---

# GOAL-018 — Engenharia de Performance Real, Cache JSON.GZ, Segurança para Monolitos e Modo Dev (`2.6.1`)

1. **Bloco A:** Cache `.polaris/cache.json.gz` atômico (sem SQLite), leitura única de disco, descarte seguro de binários/minificados (`.js`/`.mjs`/`.css`) sem pular backend por linha longa, `--include-minified`.
2. **Bloco B:** `--profile auto|low-spec|max`, prioridade reduzida nos subprocessos, `--changed-only` offline, regex pré-compilada e entropia fatiada.
3. **Bloco C:** `ast.parse()` único por arquivo `.py`, zero N+1 em `relocation.py`, ingestão em lotes (`batch_size=500`), limpeza e build web.
4. **Bloco D:** `tests/unit/scanner/test_monolith_safety.py`, benchmark comparativo, dogfooding e release `2.6.1`.
