# POLARIS — Architecture AS-IS (Fase 18)

## Estilo Arquitetural
Monólito modular com separação explícita entre Scanner (`src/polaris_scanner`), Server (`src/polaris_server`) e Analisadores Especializados (`analyzers/{python,csharp,java,sql}`).

```mermaid
flowchart LR
    CLI["CLI / Orchestrator"] --> Scanner["polaris_scanner"]
    Scanner --> PyAnl["Python Analyzer (AST/CFG)"]
    Scanner --> SqlAnl["SQL Analyzer (SQLGlot)"]
    Scanner --> CsAnl["C# Analyzer (Roslyn DLL)"]
    Scanner --> JvAnl["Java Analyzer (JavaParser JAR)"]
    PyAnl --> Contract["JSON Issues Contract"]
    SqlAnl --> Contract
    CsAnl --> Contract
    JvAnl --> Contract
    Contract --> Server["polaris_server"]
```
