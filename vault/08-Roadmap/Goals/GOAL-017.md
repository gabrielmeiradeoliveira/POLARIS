---
id: GOAL-017
title: Otimização de Performance do Motor, Cache Incremental por Hash e Calibração de Confiança
status: IN_PROGRESS
priority: HIGH
depends_on:
  - GOAL-012
  - GOAL-013
  - GOAL-014
  - GOAL-015
  - GOAL-016
version_target: 2.6.0
created: 2026-11-24
updated: 2026-11-24
owner: project
tags:
  - goal
  - release-2.6.0
  - performance
  - caching
  - parallelism
  - confidence-calibration
  - hardening
---

# GOAL-017 — Otimização de Performance do Motor, Cache Incremental por Hash e Calibração de Confiança (`2.6.0`)

## 1. Objetivo
Aumentar drasticamente a velocidade de execução do **POLARIS Scanner & Analyzers** (reduzindo em **>= 60%** o tempo de análise incremental e em **>= 40%** o tempo de análise completa) e elevar a confiabilidade operacional das detecções através de **classificação determinística de confiança (`HIGH` / `MEDIUM` / `LOW`)** e **poda de falsos positivos**.

## 2. Critérios de Aceitação (`2.6.0`)
- [x] Cache SHA-256 funcional (`cache.py`) com `--no-cache`, `--clear-cache` e invalidação automática quando o Quality Profile mudar.
- [x] Execução paralela de workers + batching único por linguagem + *Fast-Path Pre-Filter* implementados.
- [x] Campo `confidence` (`HIGH` / `MEDIUM` / `LOW`) emitido pelos analisadores, suportado nos Quality Gates e exibido na UI (`web/`).
- [x] Benchmark comprovando ganho significativo de latência (*Warm Run* `< 500ms` para diffs pequenos) e `0` falsos positivos na suíte calibrada.
- [x] Relatório registrado em `vault/09-Validation/Reports/VAL-GOAL-017-RELEASE-2.6.0.md` e `Current-State.md` promovido para **`2.6.0`**.
