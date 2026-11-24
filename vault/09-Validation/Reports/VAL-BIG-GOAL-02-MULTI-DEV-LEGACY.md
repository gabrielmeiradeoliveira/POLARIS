---
id: VAL-BIG-GOAL-02-MULTI-DEV-LEGACY
title: Relatório de Validação — BIG-GOAL-02 (GOAL-027 a GOAL-031)
status: VALIDATED
created: 2026-11-24
owner: project
tags:
  - validation
  - big-goal-02
  - legacy
  - multi-dev
---

# VAL-BIG-GOAL-02-MULTI-DEV-LEGACY

- **GOAL-027 (Multi-Projeto & Auth):** `src/polaris_server/auth_jwt.py` (`create_jwt`, `verify_jwt`, `generate_api_key`), `--limit-concurrency 10` no `uvicorn`, `test_multi_project_auth.py` (`2/2 PASS`).
- **GOAL-028 (Fingerprint & Triagem):** `src/polaris_server/triage.py` (`compute_persistent_fingerprint`, `IssueRecord.triage`), `test_issue_fingerprint_triage.py` (`1/1 PASS`).
- **GOAL-029 (Resiliência Legada):** `src/polaris_scanner/safe_reader.py` (`utf-8 -> utf-8-sig -> cp1252 -> latin-1`, `classify_file_scope`), `analyzers/legacy/polaris_legacy_analyzer.py` (`LEG-SEC-001..005`, `LEG-REL-001`), `test_legacy_resilience.py` (`3/3 PASS`).
- **GOAL-030 (Baseline & Inline Suppression):** `src/polaris_scanner/baseline.py` (`extract_suppression`, `filter_new_debt`), `test_baseline_and_suppression.py` (`2/2 PASS`).
- **GOAL-031 (SARIF 2.1.0 & Low-Spec):** `src/polaris_scanner/exporters/sarif.py`, `docker-compose.low-spec.yml` (`< 100 MiB` RSS em `docker stats --no-stream`).
