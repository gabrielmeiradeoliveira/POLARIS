# POLARIS — GOAL 30: ADVANCED CONTRACT INTELLIGENCE (FASE 30.7)

**Data:** 2026-11-08
**Status:** IMPLEMENTED
**Arquivo Principal:** `src/polaris/contracts/advanced_contract_engine.py`
**Testes:** `tests/test_advanced_contracts.py` (2 passed)

---

## 1. Especificação Implementada
- **Inspeção de Assinaturas AST:** Extração precisa de argumentos posicionais obrigatórios, parâmetros com defaults, argumentos keyword-only e anotações de tipo.
- **Detecção de Argumentos Faltantes (`MISSING_REQUIRED_ARGUMENT`):** Identificação determinística quando um chamador omite parâmetros obrigatórios que deixaram de ter defaults.
- **Detecção de Argumentos Inesperados (`UNEXPECTED_KEYWORD_ARGUMENT`):** Sinalização precisa quando chamadores passam parâmetros nomeados inexistentes para funções que não aceitam `**kwargs`.
- **Rastreabilidade:** Emissão de produtor, consumidor, linha do call site e evidência textual desparseada.
