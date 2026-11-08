# POLARIS — GOAL 30: CONTEXTRANKER 3.0 (FASE 30.9)

**Data:** 2026-11-08  
**Status:** IMPLEMENTED  
**Arquivo Principal:** `src/polaris/context/context_ranker_3.py`  
**Testes:** `tests/test_context_ranker_3.py` (1 passed)  

---

## 1. Especificação Implementada
- **Pontuação Multidimensional:** Priorização baseada em:
  - Arquivos primários alterados (Score 100.0).
  - Arquivos com alterações de comportamento registradas (Score 85.0).
  - Consumidores diretos em grafo semântico (Score 70.0).
  - Consumidores transitivos (Score 40.0).
- **Enforcement Estrito de Orçamento de Tokens:** Seleção determinística que acumula snippets até o teto `max_tokens` sem estouro de orçamento.
- **Desempate Determinístico:** Critério estável por pontuação decrescente, custo de tokens crescente e caminho lexicográfico.
