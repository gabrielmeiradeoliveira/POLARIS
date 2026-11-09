# POLARIS — GOAL 30: INCREMENTAL ANALYSIS ENGINE (FASE 30.3)

**Data:** 2026-11-08
**Status:** IMPLEMENTED
**Arquivo Principal:** `src/polaris/context/incremental_engine.py`
**Testes:** `tests/test_incremental_engine.py` (2 passed)

---

## 1. Especificação Implementada
- **Detecção de Mudanças:** Distinção precisa de arquivos `ADDED`, `MODIFIED`, `DELETED`, `RENAMED` e `UNCHANGED` através de hashing SHA-256 estável de conteúdo.
- **Invalidação Seletiva de Cache:** O método `invalidate_file` remove exclusivamente as entidades do arquivo modificado/excluído e expurga arestas conectadas (tanto de saída quanto de entrada), prevenindo nós e referências fantasmas.
- **Sincronização Incremental:** `sync_file` permite atualização atômica e pontual de grafos sem necessidade de reprocessamento do repositório inteiro.
- **Equivalência Semântica:** O estado do grafo após invalidação e reindexação incremental é equivalente a uma reconstrução a quente.
