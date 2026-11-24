---
id: VAL-POC-V3-FIELD-TRIAL
title: Relatório Final de PoC v3.0 — Campo de Provas & Calibração Empírica
status: VALIDATED
created: 2026-11-24
owner: project
tags:
  - validation
  - poc
  - v3.0
---

# VAL-POC-V3-FIELD-TRIAL

- **Corpus Hostil Poliglota (`poc/torture_corpus_generator.py`):** 12 arquivos hostis (encoding `cp1252`, binário disfarçado, bundle `.min.js` 50k chars, Terraform, TSX, PHP, Shell, Kotlin, Rust, C, `web.config`, `tests/test_dummy.py`).
- **Resultado:** `0` `file_errors`, `2` arquivos descartados (`fake_image.py`, `vendor.min.js`), detecção ativa em todas as linguagens.
- **Orçamento Low-Spec (`docker-compose.low-spec.yml`):** `93.14 MiB` total (`< 1200 MiB`), `0` OOMs.
