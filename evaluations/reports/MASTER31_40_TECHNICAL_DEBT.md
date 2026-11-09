# POLARIS — MASTER GOAL 31–40: TECHNICAL DEBT LEDGER
## Architecture Health, Refactoring Roadmap & Smells Registry

**Status:** AUDITED (Fase A)
**Date:** 2026-11-08

---

### 1. Identified Technical Debt Areas

#### 1.1 Multi-Language AST Analysis Scope
- **Current State:** Static analysis visitors (`src/polaris/analysis/`) and AST extractors operate primarily on Python source files using standard library `ast`.
- **Debt Impact:** Supply chain (GOAL 31) and container scanning (GOAL 32) analyze `requirements.txt`, `package-lock.json`, and `Dockerfile` deterministically, but code taint tracking is currently Python-focused.
- **Future Action:** Integrate tree-sitter or language server protocol (LSP) parsers for polyglot semantic analysis (TypeScript, Go, Rust).

#### 1.2 Orchestrator Inheritance Chain
- **Current State:** `HybridOrchestrator3` inherits from `HybridReviewOrchestrator`, extending it with multi-agent context fusion and interprocedural analysis.
- **Debt Impact:** Two orchestrator entrypoints exist in the codebase.
- **Remediation Strategy:** Unify under `HybridReviewOrchestrator` via a strategy/plugin pattern once legacy GOAL 28 test suites are formally migrated to v3 interfaces.

#### 1.3 Legacy Forwarding Package (`src/deicide/`)
- **Current State:** Two-file stub forwarding `deicide` imports to `polaris.cli`.
- **Debt Impact:** Redundant directory retained for backward compatibility.
- **Remediation Strategy:** Deprecate across two minor releases, issuing a `DeprecationWarning` on CLI invocation before final deletion.

---

### 2. Code Quality Metrics & Verification Status
- **Automated Tests:** 556 tests passing across all components.
- **Flakiness / Network Reliance:** 0% — completely decoupled from external network access, fully offline deterministic execution.
- **Frozen GOAL 27 Integrity:** 100% verified (SHA-256 matches baseline).
