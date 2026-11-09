# POLARIS — GOAL 34: TOKEN-OPTIMIZED AI VALIDATION GATEWAY

**Data:** 2026-11-08
**Status:** **ACCEPTED WITH LIMITATIONS**
**Implementação:** `src/polaris/gateway/validation_gateway.py`
**Testes:** `tests/test_gateway_and_validator.py`

---

## 1. Capacidades
- Skip Policy estrito: achados determinísticos confirmados e de risco controlado não acionam IA (`DETERMINISTIC_CONFIRMED`).
- Cache persistente por hash determinístico SHA-256 (`finding_id` + diff).
- Compressão de contexto direcionada ao invés de envio indiscriminado de arquivos.
- Controle fail-closed sobre orçamento de tokens (`BUDGET_EXHAUSTED`).
