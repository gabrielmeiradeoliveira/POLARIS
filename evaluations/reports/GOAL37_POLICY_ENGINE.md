# POLARIS — GOAL 37: SECURITY QUALITY GATES & POLICY ENGINE

**Data:** 2026-11-08
**Status:** **ACCEPTED WITH LIMITATIONS**
**Implementação:** `src/polaris/policy/quality_gate.py`
**Testes:** `tests/test_github_gate_and_sarif.py`

---

## 1. Capacidades
- Decisões de CI configuráveis: `PASS`, `WARN`, `FAIL`, `INCONCLUSIVE`.
- Política baseada em severidade (`fail_on_severity: ["CRITICAL", "HIGH"]`).
- Fluxo auditável de supressão de achados (`suppressed_finding_ids`).
