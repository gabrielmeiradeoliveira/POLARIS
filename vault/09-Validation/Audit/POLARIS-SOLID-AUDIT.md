# POLARIS — SOLID & Design Principles Audit (Fase 20)

## Violações Concretas Identificadas
1. **SRP / OCP — `analyzers/csharp/Program.cs` e `analyzers/java/.../PolarisJavaAnalyzer.java`:**
   - Misturam CLI parsing, leitura de arquivos, regras inline do piloto e serialização JSON.
   - Alternativa proposta: migrar gradualmente as 5 regras inline do piloto para `CSharpRulesEngine` / `JavaRulesEngine` com testes de equivalência.
2. **DIP — `scripts/validation/catalog_batch_runner.py`:**
   - Acoplava-se diretamente a `vault/.../batch_state.json` sem abstração de diretório de estado; mitigado com `--state-dir` e `POLARIS_STATE_DIR`.
