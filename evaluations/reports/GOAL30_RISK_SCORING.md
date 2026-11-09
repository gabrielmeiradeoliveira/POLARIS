# POLARIS — GOAL 30: EXPLAINABLE RISK SCORING (FASE 30.11)

**Data:** 2026-11-08
**Status:** IMPLEMENTED
**Arquivo Principal:** `src/polaris/intelligence/risk_scoring.py`
**Testes:** `tests/test_risk_scoring.py` (1 passed)

---

## 1. Especificação Implementada
- **Decomposição Auditável (`RiskBreakdown`):** Apresentação explícita de `base_severity_score`, `confidence_weight`, `architectural_exposure_multiplier` e `final_score`.
- **Determinismo e Transparência:** Zero números arbitrários sem rastreamento; o texto explicativo decompõe cada componente multiplicador.
- **Níveis de Risco Calibrados:** Mapeamento explícito para faixas `CRITICAL`, `HIGH`, `MEDIUM` e `LOW`.
