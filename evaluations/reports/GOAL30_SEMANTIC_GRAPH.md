# POLARIS — GOAL 30: SEMANTIC PROJECT GRAPH (FASE 30.2)

**Data:** 2026-11-08
**Status:** IMPLEMENTED
**Arquivo Principal:** `src/polaris/context/semantic_graph.py`
**Testes:** `tests/test_semantic_graph.py` (3 passed)

---

## 1. Especificação Implementada
- **Entidades:** `FILE`, `MODULE`, `CLASS`, `FUNCTION`, `METHOD`, `SYMBOL`, `IMPORT`, `CALL`, `CONTRACT`, `ENDPOINT`.
- **Arestas:** `IMPORTS`, `DEFINES`, `CALLS`, `REFERENCES`, `INHERITS`, `CONSUMES`, `RETURNS`, `DEPENDS_ON`.
- **Certeza:** `CONFIRMED`, `POSSIBLE`, `INFERRED`.
- **IDs Determinísticos:** Função hash SHA-256 baseada em tipo, caminho normalizado e assinatura de linha.
- **Detecção de Ciclos:** Algoritmo DFS com controle de profundidade e rastreamento de pilha de recursão.
- **Persistência Atômica:** Escrita segura via arquivo temporário com substituição atômica (`.replace()`) e fallback automático para índice limpo em caso de JSON corrompido ou versão de schema incompatível.
