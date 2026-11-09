# POLARIS — MASTER GOAL 31–40: CODEBASE AUDIT REPORT
## Fase 9.1: Comprehensive Inventory, Dead Code Elimination & Technical Debt Audit

**Status:** AUDITED (Fase A: Zero-Deletion Proposal Mode)
**Date:** 2026-11-08
**Scope:** `src/`, `tests/`, `evaluations/`, configuration, root transients, and dependency tree.
**Strict Policy:** No files deleted or moved in Fase A. GOAL 27 frozen artifacts fully protected.

---

### 1. Repository Inventory by Directory

#### 1.1 `src/` (Production & Core Engine)
- `src/polaris/`:
  - `core/`: Core domain models (`models.py`, `rule_engine.py`, `context_ranker.py`, `context_ranker_3.py`, `ast_service.py`, `risk_scoring.py`, `evidence_fusion.py`).
  - `orchestration/`: Multi-agent orchestration and review workflows (`orchestrator.py`, `orchestrator_3.py`, `budget.py`, `arbitration.py`).
  - `analysis/`: Static analysis AST visitors, taint engines, and cross-file contract checkers.
  - `supply_chain/`: **(GOAL 31)** SBOM generator (CycloneDX 1.5) and lockfile vulnerability scanner (`scanner.py`).
  - `container/`: **(GOAL 32)** Dockerfile deterministic static security analyzer (`scanner.py`).
  - `evidence/`: **(GOAL 33)** Unified Canonical Security Finding model and platform fusion (`platform.py`).
  - `gateway/`: **(GOAL 34)** Token-Optimized AI Validation Gateway (`validation_gateway.py`).
  - `validator/`: **(GOAL 35)** AI Validation and remediation advisor (`ai_validator.py`).
  - `integrations/github/`: **(GOAL 36)** GitHub App HMAC webhook and PR review integration (`review_native.py`).
  - `policy/`: **(GOAL 37)** Declarative Quality Gate evaluator (`quality_gate.py`).
  - `reporting/`: **(GOAL 38)** SARIF v2.1.0 generator (`sarif.py`).
  - `cli.py`: Public entry point with subcommands for review, supply-chain, container, gate, sarif, and validate.
- `src/deicide/`:
  - Legacy package alias retained from prior product identity ("Deicide").
  - `src/deicide/__init__.py`, `src/deicide/__main__.py`: Lightweight forwarder importing `from polaris.cli import main`.
  - **Classification:** `ARCHIVE` / `REFACTOR` (Safe to remove if backward compatibility alias is discontinued, or retain as a zero-overhead compatibility bridge).

#### 1.2 `tests/` (Verification Suites)
- **Status:** 556 passing tests across unit, integration, and platform end-to-end suites.
- Core suites: `test_supply_chain.py`, `test_container_security.py`, `test_unified_evidence_platform.py`, `test_gateway_and_validator.py`, `test_github_gate_and_sarif.py`, `test_hybrid_orchestrator.py`, `test_orchestrator_3.py`, `test_continuous_platform_goal51.py`, `test_goal27_runner.py`.
- **Classification:** `KEEP`.

#### 1.3 `evaluations/` (Benchmarks, Reports & Datasets)
- `evaluations/fixtures/`:
  - `end_to_end_context_benchmark.json`: Frozen GOAL 27 test set (SHA-256: `1901684d...`). **PROTECTED**.
  - `bug_intro_03_temp.json`, `bug_intro_04_05_temp.json`, `clean_negatives_temp.json`: Transient evaluation subsets created during GOAL 27 audit script iterations. **DELETE_CANDIDATE** (Fase B).
- `evaluations/results/`:
  - `goal27_smoke_test/results.json`: Frozen smoke test result (SHA-256: `ba726b7d...`). **PROTECTED**.
  - `goal27_offline_sim/`, `goal27_offline_test/`, `goal27_minimax_real/`: Historical evaluation output runs. **KEEP** / **PROTECTED**.
- `evaluations/manifests/`:
  - `goal27-model-selection.json`: Frozen experiment manifest (SHA-256: `d6eebda0...`). **PROTECTED**.
- `evaluations/goal39_benchmark.py`: Comprehensive 5-domain evaluation harness (GOAL 39). **KEEP**.
- `evaluations/reports/`: Complete technical reports for GOALS 27-40. **KEEP**.

#### 1.4 Ephemeral & Log Files (Root Directory)
- `pytest_full_output.txt`, `pytest_goal30_closing.txt`, `pytest_goal30_full.txt`, `pytest_final_audit.txt`, `pytest_master31_40_full.txt`: Test execution console stdout dumps. **DELETE_CANDIDATE** (Fase B).
- `.pytest_temp/`: Pytest cache / temporary test run directories. **DELETE_CANDIDATE** (Fase B, tracked in `.gitignore`).
- `demo-repo/`: Temporary test directory created by local exploratory tests. **DELETE_CANDIDATE** (Fase B, tracked in `.gitignore`).

---

### 2. Dead Code & Technical Debt Analysis

1. **AST / File Duplication in Context Ranking:**
   - Both `context_ranker.py` and `context_ranker_3.py` exist in `src/polaris/core/`.
   - `context_ranker_3.py` extends `ContextRanker` with interprocedural call-graph topology and behavioral delta integration.
   - *Recommendation:* Keep `context_ranker.py` as base class / stable contract and `context_ranker_3.py` as topological specialization.
2. **Double Orchestrator Hierarchy:**
   - `src/polaris/orchestration/orchestrator.py` (`HybridReviewOrchestrator`) and `src/polaris/orchestration/orchestrator_3.py` (`HybridOrchestrator3`).
   - `HybridOrchestrator3` inherits directly from `HybridReviewOrchestrator` to inject topological context ranking and multi-agent evidence fusion while preserving all budget, guardrail, and arbitration policies.
   - *Recommendation:* Retain both; clean inheritance ensures backwards-compatibility for existing tests.
3. **Legacy Package Bridge (`src/deicide/`):**
   - The repository historically moved from Deicide to POLARIS. The forwarder in `src/deicide/__main__.py` ensures backwards CLI invocations (`python -m deicide`) route to `polaris.cli:main`.
   - *Recommendation:* Tag as `ARCHIVE`; delete only if compatibility with older scripts is officially dropped.
