---
id: VAL-GOAL-019-RELEASE-2.7.0
title: Relatório de Validação — GOAL-019 (Release 2.7.0)
status: VALIDATED
created: 2026-11-24
owner: project
tags:
  - validation
  - goal-019
  - release-2.7.0
---

# VAL-GOAL-019-RELEASE-2.7.0

## 1. Validado Localmente (Neste Host)
- **Warm Cache Real (`--cache-dir`):** `252.19 ms` (`-93.2%` vs Cold Run `3736.83 ms`).
- **Calibração Real (`tests/calibration/test_precision_calibration.py`):**
  - `python`: `TP=3, FP=0, FN=0, FP%=0.0%`
  - `sql`: `TP=3, FP=0, FN=0, FP%=0.0%`
  - `typescript`: `TP=3, FP=0, FN=0, FP%=0.0%`
- **Suíte Local:** `13 / 13` testes aprovados (`OK`).

## 2. Validado via CI Matrix (`.github/workflows/ci-matrix.yml`)
- `scanner-go` (Go 1.23, `go test ./...`, build Linux/Windows, paridade).
- `workers-dotnet-java` (.NET 8 + JDK 17).
- `web-build` (`npm --prefix web ci && npm --prefix web run build`).
