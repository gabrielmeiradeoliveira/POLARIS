# POLARIS — Architecture TO-BE (Fase 19)

## Decisão
Manter **Modular Monolith** para `polaris_server` e **Specialized Subprocess Analyzers** para `analyzers/*`, evitando microserviços ou IR universal prematura.

## Regras de Dependência
1. `polaris_scanner` nunca importa `polaris_server` (validado em `tests/test_architecture_fitness.py`).
2. Comunicação entre Scanner/Server e Analisadores ocorre exclusivamente via contrato JSON versionado.
3. Cada analisador mantém semântica especializada na sua linguagem (Roslyn, JavaParser, AST/CFG Python, SQLGlot).
