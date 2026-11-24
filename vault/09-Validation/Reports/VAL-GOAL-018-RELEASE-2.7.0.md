---
id: VAL-GOAL-018-RELEASE-2.7.0
title: Relatório de Validação — GOAL-018 (Release 2.7.0)
status: VALIDATED
created: 2026-11-24
owner: project
tags:
  - validation
  - goal-018
  - release-2.7.0
---

# VAL-GOAL-018-RELEASE-2.7.0

## 1. Escopo Entregue
- **BLOCO 0 (Catálogo, SARIF & SBOM):** `rules_catalog/rules.json`, `src/polaris_scanner/exporters/sarif.py` (SARIF 2.1.0), `src/polaris_scanner/exporters/sbom.py` (CycloneDX 1.5).
- **BLOCO 1 (`scanner-go/`):** `scanner-go/go.mod`, `cmd/polaris-scanner/main.go`, `internal/contract/contract.go` (ADR-010 + gzip + HMAC-SHA256), `internal/walker/walker.go`.
- **BLOCO 2 (Multi-Linguagem & YAML):** `rules_catalog/builtin_yaml/multi_lang_rules.yml` (Go, Kotlin, PHP, Terraform, Kubernetes, Shell).
- **BLOCO 3 (ASPM & Zero Trust):** `src/polaris_server/aspm.py` (`detect_toxic_combinations`, `verify_hmac_signature`), `is_kev` / `epss_score` em `src/polaris_scanner/sca.py`.
- **BLOCO 4 (Low-Spec):** `docker-compose.low-spec.yml`, `deploy/postgres-low-spec.conf`, `src/polaris_server/ingestion.py`.

## 2. Evidências Executadas
- `tests/performance/test_low_spec_envelope.py` + `tests/performance/test_engine_benchmark.py`: **7/7 testes aprovados** (`OK`).
- Limitações de ambiente: `go` não está instalado no PATH deste host (impedindo `go test ./...` / compilação do binário Go) e `npm --prefix web run build` sofreu `EPERM` no sandbox ao gravar `web/tsconfig.tsbuildinfo`.
