---
id: GOAL-019
title: Consolidação de Produto Intermediário — Warm Cache Real, Binário Go + Regras YAML, Calibração de Precisão e Distribuição Plug-and-Play
status: IN_PROGRESS
priority: HIGH
depends_on:
  - GOAL-018
version_target: 2.7.0
created: 2026-11-24
updated: 2026-11-24
owner: project
tags:
  - goal
  - release-2.7.0
  - warm-cache
  - golang
  - yaml-rules
  - battle-testing
  - low-spec
  - distribution
  - aspm
---

# GOAL-019 — Consolidação de Produto Intermediário (`2.7.0`)

1. **BLOCO 1:** Warm Cache real (`<= 500 ms`), `--format sarif` & `--sbom-out` no CLI, integração ASPM/HMAC/streaming e retenção PostgreSQL (`retention.py`).
2. **BLOCO 2:** `scanner-go/` (pendente `go` no PATH deste host).
3. **BLOCO 3:** Calibração de falsos positivos (`tests/calibration/`) com taxa `< 10%` em alertas `HIGH`.
4. **BLOCO 4:** `.pre-commit-hooks.yaml`, `.github/workflows/polaris-reusable.yml`, `docs/QUICKSTART.md` e Release `2.7.0`.
