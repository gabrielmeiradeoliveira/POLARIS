# POLARIS — GOAL 29.1: Baseline de Arquitetura e Engenharia Offline

> **Documento:** `GOAL29_BASELINE.md`  
> **Data:** 2026-11-08T02:39:00Z  
> **Branch Base:** `feat/goal29-ultimate-offline-engineering` (após commit `ac35eb5`)  
> **Status:** Baseline Inicial Aprovado (515/515 testes passando)

---

## 1. Inventário de Componentes e Estado Real

1. **CLI (`src/polaris/cli.py`):**
   - Suporta comandos `review` e subcomandos `github`.
   - Estratégia padrão: `direct` (pipeline `AnalysisOrchestrator`).
   - Estratégia experimental opt-in: `hybrid` (`HybridReviewOrchestrator`).
2. **AST e Grafo de Dependências (`src/polaris/context/`):**
   - `ProjectIndex`: Mapeia símbolos, classes, funções e imports globais.
   - `DependencyGraph`: Grafo direcionado de dependências entre arquivos e nós.
   - `BehavioralDeltaEngine`: Extrai assinaturas, chamadores e testes afetados por AST.
   - `ContextRanker`: Ranqueador de trechos com orçamento rígido de tokens.
3. **Controle de Orçamento e Cota (`src/polaris/core/models.py`, `src/polaris/quota/store.py`):**
   - `ExecutionBudget`: Limites de tokens (total, prompt, completion), requests e timeouts.
   - `BudgetTracker`: Controle atômico com reservas (`reserve_attempt`, `complete_attempt`).
   - `UsageStore`: Persistência SQLite com controle de concorrência e rate limit (RPM, TPM, RPD).
4. **Motor Híbrido (`src/polaris/guardrails/`, `contracts/`, `intelligence/`, `review/`):**
   - `SecurityGuardrailEngine`: Regra `SEC-AUTH-001` (detecção AST de relaxamento de acesso).
   - `CrossFileContractEngine`: Rastreamento interprocedural de retorno e consumidores.
   - `FindingArbitrationEngine`: 6 regras formais de resolução, proveniência e deduplicação.
   - `HybridReviewOrchestrator`: Pipeline em 5 estágios (Estático -> OFF -> Política -> ON -> Arbitragem).

---

## 2. Métricas do Baseline Inicial

- **Suíte de Testes Geral:** 515 passed, 0 failed, 1 warning (30.11s).
- **Cobertura Funcional Offline:**
  - 486 testes do core, git, contexto, providers fake e orquestrador direto.
  - 29 testes dos módulos do GOAL 28 (guardrails, contratos, arbitragem, orquestrador híbrido).
