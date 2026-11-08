# POLARIS — GOAL 30: AUDITORIA ARQUITETURAL PROFUNDA (FASE 30.1)

**Data:** 2026-11-08
**Branch:** `feat/goal30-autonomous-code-intelligence`
**Base:** `64e21f9777f6872b41caa49c803a8eaac2231676`
**Status do Baseline:** 525/525 testes aprovados em 69.76s

---

## 1. Visão Geral dos Módulos Existentes

1. **CLI (`src/polaris/cli.py`):**
   - Suporta comandos: `review`, `batch`, `eval`, `report`, `diff`, `init`.
   - Estratégia padrão: `DIRECT`.
   - Flags opt-in: `--strategy hybrid`, `--offline`, etc.
   - Ponto de atenção: Compatibilidade retroativa rígida; novos relatórios e metadados devem ser adicionados como opt-in ou em campos complementares sem quebrar saídas JSON existentes.

2. **Hybrid Review Engine (`src/polaris/review/`):**
   - `HybridReviewOrchestrator`: Gerencia o fluxo de 5 estágios (Análise Estática, Arm OFF, Política de Expansão, Arm ON via ContextRanker, Arbitragem).
   - `ExpansionPolicy`: Avalia necessidade de expansão com base em achados estáticos e orçamento restante.
   - Ponto de extensão: O pipeline do GOAL 30 (Fase 30.12) integrará o grafo semântico, delta comportamental 3.0, impacto interprocedural, fluxo de dados e pontuação de risco explicável.

3. **Context & Semantic Analysis (`src/polaris/context/`):**
   - `ProjectIndex`: Mapeamento de arquivos e símbolos.
   - `DependencyGraph`: Grafo direcionado simples baseado em imports e chamadas lexicais.
   - `ContextRanker`: Ranqueamento por prioridades (Prio 0 a Prio 3) e restrições de token.
   - `BehavioralDelta`: Comparador AST preliminar para alterações em funções.
   - Ponto de atenção: Limitação atual no tratamento de importações relativas complexas e chamadas indiretas/reexports; a Fase 30.2 (Semantic Project Graph) e 30.8 (Behavioral Delta 3.0) solucionarão essas lacunas.

4. **Guardrails & Contratos (`src/polaris/guardrails/`, `src/polaris/contracts/`):**
   - `SecurityGuardrailEngine`: Regras de autorização, injeção de SQL e bypass incondicional (`SEC-AUTH-002`).
   - `CrossFileContractEngine`: Detector de mudanças de contrato de chamadas e retornos incompatíveis (dicionários vs tuplas/listas).
   - Ponto de extensão: As Fases 30.6 e 30.7 estenderão os contratos para assinaturas completas (TypedDict, Dataclass, kwargs/defaults) e novas regras determinísticas de segurança com comparação before/after.

5. **Arbitragem & Orçamento (`src/polaris/arbitration/`, `src/polaris/core/models.py`):**
   - `FindingArbitrationEngine`: Deduplicação e arbitragem por confiança entre achados estáticos e LLM.
   - `BudgetTracker`: Controle estrito de tokens e requisições, thread-safe, com reserva atômica (`reserve_attempt`, `complete_attempt`).

---

## 2. Mapa de Dependências e Arquitetura

```text
[CLI / API]
     │
     ▼
[HybridReviewOrchestrator]
     ├─► [SemanticProjectGraph & Incremental Engine] (Fases 30.2, 30.3)
     ├─► [BehavioralDelta 3.0] (Fase 30.8)
     ├─► [InterproceduralImpactAnalysis] (Fase 30.4)
     ├─► [DataflowAnalysisEngine] (Fase 30.5)
     ├─► [SecurityIntelligenceEngine] (Fase 30.6)
     ├─► [AdvancedContractIntelligence] (Fase 30.7)
     ├─► [EvidenceFusionEngine] (Fase 30.10)
     ├─► [ContextRanker 3.0] (Fase 30.9)
     ├─► [LLM Providers: Fake/Scripted/Direct]
     ├─► [Arbitration & RiskScoring] (Fase 30.11)
     └─► [Reporting & JSON Explicabilidade] (Fase 30.13)
```

---

## 3. Identificação de Riscos e Pontos Críticos

1. **Preservação do GOAL 27:** Nenhum arquivo em `evaluations/fixtures/`, `evaluations/results/goal27*`, ou `evaluations/manifests/` deve ser alterado.
2. **Determinismo:** Todas as operações do Semantic Graph e Dataflow devem ser 100% determinísticas em ordenação de nós, deduplicação de hashes SHA-256 e pontuação de risco.
3. **Isolamento de Ambiente e Compatibilidade:** O ambiente do Windows requer caminhos normalizados POSIX (`/`), tratamento de case-insensitive em caminhos de arquivo e ausência de sockets de rede externos.

---

## 4. Baseline Executável
- **Commit Base:** `64e21f9777f6872b41caa49c803a8eaac2231676`
- **Total de Testes Atuais:** 525 aprovados.
- **Modo Padrão:** DIRECT preservado.
