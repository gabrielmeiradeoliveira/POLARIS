---
id: ADR-005-AGNOSTIC-AI-V3
title: ADR-005 — Camada de IA Híbrida & Agnóstica (v3.0 + v3.1)
status: VALIDATED
created: 2026-11-24
owner: project
tags:
  - adr
  - ai
  - v3.0
  - v3.1
---

# ADR-005 — Camada de IA Híbrida & Agnóstica (`v3.0` + `v3.1`)

- **Adaptador Universal (`/v1/chat/completions`):** `src/polaris_server/ai/provider.py` (`urllib.request`, zero SDKs pesados).
- **Calibração Adaptativa (`src/polaris_server/ai/service.py`):** `500` tokens (moderno) vs `1200` tokens (monolito legado), cache por `(fingerprint, snippet_hash, model)` e teto diário `POLARIS_AI_DAILY_TOKEN_BUDGET`.
- **Disparo Manual:** `GET /api/ai/status` e `POST /api/issues/{issue_id}/ai-analyze` apenas sob clique no Cockpit `v3.1`.
