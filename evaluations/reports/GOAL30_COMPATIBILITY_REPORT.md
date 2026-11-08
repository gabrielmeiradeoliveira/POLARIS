# POLARIS — GOAL 30: CLI, JSON E EXPLICABILIDADE (FASE 30.13)

**Data:** 2026-11-08  
**Status:** IMPLEMENTED  
**Arquivo Principal:** `src/polaris/cli.py`  
**Testes:** `tests/test_cli_goal30.py` (1 passed)  

---

## 1. Especificação Implementada
- **Compatibilidade Pública Estrita:** Nenhuma quebra de interface de CLI; os comandos padrão continuam aceitando a mesma sintaxe e os mesmos códigos de saída (`ExitCode`).
- **Modo Padrão `DIRECT` Preservado:** A análise direta continua operando como padrão sem exigir modelos de inteligência híbrida caso o usuário não informe `--strategy hybrid`.
- **Prevenção de Vazamento de Segredos:** Dados de credenciais e tokens são filtrados e nunca expostos em saídas de erro ou formato JSON público.
