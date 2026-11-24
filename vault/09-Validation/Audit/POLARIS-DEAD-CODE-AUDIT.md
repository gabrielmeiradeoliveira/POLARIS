# POLARIS — Dead Code & Redundancy Audit (Fase 17)

## Achados Classificados
- **`LEGACY` / `DUPLICATED`:** Regras do piloto (`*-SYN-001`, `*-SEM-001`, `*-REL-001`, `*-SEC-001`, `*-MNT-001`) ainda possuem implementação inline em `Program.cs` e `PolarisJavaAnalyzer.java` além de constarem em `CSharpRulesEngine` e `JavaRulesEngine` (atualmente filtradas por `pilotRuleIds` para evitar duplicação).
- **`ACTIVE`:** `ControlFlowGraph`, `WorklistSolver`, `NullabilityAnalysis`, `ResourceStateAnalysis`, `DeadStoreAnalysis` em `analyzers/python/semantic_engine.py`.
- **`EXPERIMENTAL`:** Diretório `poc/` separado do código de produção.
