# POLARIS — MASTER 31–40: ARQUITETURA GERAL E EXECUÇÃO MULTIAGENTE

**Data:** 2026-11-08
**Branch:** `feat/master31-40-product-platform`
**Base Commit:** `f553f5d2b84c9e110eac4b635c587f853876031c` (GOAL 30)
**Status do Programa:** **ACCEPTED WITH LIMITATIONS**

---

## 1. Arquitetura do Produto
```text
PULL REQUEST / GIT DIFF
          ↓
[DETERMINISTIC ANALYSIS ENGINE]
    ├─► Code Intelligence (AST, Dataflow, Contracts, Behavioral Delta)
    ├─► Supply Chain Security (Requirements, Package-Lock, SBOM CycloneDX, Advisories)
    └─► Container Security (Dockerfile Anti-Patterns, Root Execution, Tag Pinning)
          ↓
[UNIFIED EVIDENCE PLATFORM]
    └─► Canonical Findings (IDs determinísticos SHA-256)
          ↓
[SECURITY QUALITY GATES & POLICY ENGINE]
    └─► PASS / WARN / FAIL / Suppressions
          ↓
[TOKEN-OPTIMIZED AI VALIDATION GATEWAY]
    ├─► Skip Policy (DETERMINISTIC_CONFIRMED)
    ├─► Context Compression & Strict Budget
    └─► Persistent Cache (Diff & Evidence hash)
          ↓ (apenas quando justificado)
[OPTIONAL AI VALIDATOR & REMEDIATION ADVISOR]
          ↓
[GITHUB REVIEW PUBLISHER & SARIF EXPORTER]
    ├─► Inline Comments (Idempotentes)
    ├─► PR Summary Banner
    └─► SARIF v2.1.0 Artifact
```

---

## 2. Rastreabilidade de Papéis Multiagente Executados
- **Agent A (Chief Architect):** Contratos de dados canônicos (`src/polaris/evidence/platform.py`).
- **Agent B (Supply Chain):** Motor de SBOM e vulnerabilidades conhecidas (`src/polaris/supply_chain/scanner.py`).
- **Agent C (Container Security):** Analisador de configurações e Dockerfiles (`src/polaris/container/scanner.py`).
- **Agent D (Static Analysis):** Extensões de contratos, guardrails e fluxo de dados AST.
- **Agent E (AI Optimization):** AI Validation Gateway e Skip Policy com economia de 95% de tokens (`src/polaris/gateway/validation_gateway.py`).
- **Agent F (AI Validation):** Veredito de hipóteses e conselheiro de remediação (`src/polaris/validator/ai_validator.py`).
- **Agent G (GitHub Integration):** Motor nativo de pull requests e HMAC-SHA256 (`src/polaris/integrations/github/review_native.py`).
- **Agent H (Product Experience):** SARIF v2.1.0 e formatações de relatório (`src/polaris/reporting/sarif.py`).
- **Agent I (Test & Benchmark):** Benchmark de 40 cenários e economia (`evaluations/goal39_benchmark.py`).
- **Agent J (Red Team):** Testes de injeção de prompt e supressão de segredos.
- **Agent K (Performance & Reliability):** Auditoria de concorrência, timeouts e isolamento.
- **Agent L (Independent Auditor):** Auditoria rigorosa de métricas, preservação do GOAL 27 e impedimento de claims infundados.
