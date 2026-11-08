# POLARIS — GOAL 30: DATAFLOW ANALYSIS ENGINE (FASE 30.5)

**Data:** 2026-11-08
**Status:** IMPLEMENTED
**Arquivo Principal:** `src/polaris/context/dataflow_engine.py`
**Testes:** `tests/test_dataflow_engine.py` (2 passed)

---

## 1. Especificação Implementada
- **Def-Use Chains & Taint Propagation:** Rastreamento estático de variáveis contaminadas originadas em fontes de entrada não confiáveis (`request.args`, `request.form`, `params`, etc.).
- **Propagação Composta:** Suporte a formatação com f-strings (`ast.JoinedStr`) e atribuições encadeadas.
- **Detecção de Sinks:** Identificação determinística de passagem de taint em sinks críticos (`cursor.execute`, `os.system`, `subprocess.run`, `eval`, etc.).
- **Sanitizadores:** Reconhecimento de filtros de cast e escape (`int()`, `escape()`, `quote()`) para supressão rigorosa de falsos positivos.
- **Status Explicáveis:** Emissão de estados `PROVEN`, `POSSIBLE` e `UNKNOWN` com linhas e evidências textuais da propagação.
