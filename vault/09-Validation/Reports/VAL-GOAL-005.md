---
id: VAL-GOAL-005
title: Relatório de Validação — GOAL-005 (Pipeline Definitivo de Análise)
type: validation-report
status: COMPLETED
created_at: 2026-11-15
updated_at: 2026-11-15
tags: [validation, goal-005, pipeline, analyze]
---

# Relatório de Validação — GOAL-005

- **Estado:** `COMPLETED` (`4/4 PASS` em [GOAL-005.json](file:///C:/Users/gabri/OneDrive/%C3%81rea%20de%20Trabalho/POLARIS%202.0/vault/09-Validation/Acceptance/GOAL-005.json))
- **Entregas:** Subcomando `polaris-scanner analyze` (`--target`, `--project`, `--server`, `--config`, `--output`, `--verbose`), `compute_issue_fingerprint` SHA-256 determinístico em `src/polaris_scanner/contracts.py`, envio conectado ao `polaris_server` e persistência em PostgreSQL 17.
- **Evidência:** `tests/integration/scanner/test_analyze_command.py` (`1/1 OK`, 4 linguagens, 8 issues com fingerprints SHA-256).
