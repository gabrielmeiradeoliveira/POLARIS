# POLARIS — GOAL 30: SECURITY INTELLIGENCE ENGINE (FASE 30.6)

**Data:** 2026-11-08
**Status:** IMPLEMENTED
**Arquivo Principal:** `src/polaris/guardrails/authorization.py`
**Testes:** `tests/test_security_path_traversal.py`, `tests/test_security_guardrails_2.py`

---

## 1. Especificação Implementada
- **Regra `SEC-AUTH-001`:** Detecção de relaxamento de autorização allow-by-default (`or role is None`).
- **Regra `SEC-AUTH-002`:** Detecção determinística de bypass incondicional de autenticação/permissões (`return True` substituindo cheques condicionais prévios).
- **Regra `SEC-PATH-001`:** Detecção determinística de sequências perigosas de travessia de diretório (`../`) introduzidas diretamente em chamadas de abertura de arquivos no sistema operacional (`open()`).
- **Comparação Before vs After:** Análise diferencial semântica que garante que apenas vulnerabilidades recém-introduzidas no diff sejam sinalizadas com grau de confiança `CONFIRMED`.
