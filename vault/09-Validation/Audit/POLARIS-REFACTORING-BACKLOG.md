# POLARIS — Refactoring Backlog (Fase 29)

1. **[P0] Recompilar C# e Java** após correções de `CS-REL-005` e `JV-REL-002` fora do sandbox.
2. **[P1] Consolidar regras do piloto** de `Program.cs` e `PolarisJavaAnalyzer.java` para `CSharpRulesEngine` e `JavaRulesEngine` com testes de equivalência.
3. **[P1] Completar fixtures restantes** (119 regras sem fixture em Python, C# e Java).
4. **[P2] Tratar `PY-SEM-NULL-001` no próprio `src/`** (148 ocorrências detectadas no dogfooding).
5. **[P2] Unificar percurso AST** em `analyzers/python/rules_engine.py` para reduzir múltiplos `ast.walk`.
