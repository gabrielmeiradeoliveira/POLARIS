# POLARIS — MASTER GOAL 31–40: PROPOSTA DE LIMPEZA ESTRUTURAL
## Segunda Auditoria de Dívida Técnica: Módulos, Engines, Benchmarks e Relatórios

**Status:** PROPOSTA / AUDITORIA ESTRUTURAL (Zero alterações sem autorização explícita)
**Data:** 2026-11-08

Esta auditoria foca exclusivamente na dívida estrutural acumulada entre os GOALS 01 a 40, classificando módulos, duplicatas de engine, scripts de benchmarks descontinuados e arquivos históricos de relatórios.

---

### 1. Engines e Orquestradores Duplicados

| Componente | Caminhos Envolvidos | Diagnóstico Técnico | Classificação | Recomendação de Engenharia |
| :--- | :--- | :--- | :--- | :--- |
| **Review Orchestrator** | `src/polaris/core/orchestrator.py` vs `src/polaris/review/orchestrator_3.py` | `orchestrator_3.py` herda de `HybridReviewOrchestrator` e adiciona análise topológica e fusão de evidências. Ambos continuam ativos porque testes legados importam da raiz de `core/`. | **REFACTOR** | Consolidar no próximo ciclo maior sob `src/polaris/review/orchestrator.py`, mantendo `core/orchestrator.py` apenas como import de redirecionamento antes de sua descontinuação gradual. |
| **Context Ranker** | `src/polaris/context/context_ranker.py` vs `src/polaris/context/context_ranker_3.py` | `context_ranker_3.py` estende o ranker base para incluir ordenação topológica interprocedural. | **REFACTOR** | Mesclar os métodos topológicos na classe base `ContextRanker` via injeção opcional de grafo semântico, eliminando a terminação `_3`. |
| **Behavioral Delta** | `src/polaris/context/behavioral_delta.py` vs `src/polaris/context/behavioral_delta_3.py` | `behavioral_delta_3.py` estende a extração de delta com contratos interprocedurais e mutações semânticas. | **REFACTOR** | Unificar os coletores de delta comportamental em uma única API canônica. |
| **Alias Legado Deicide** | `src/deicide/` (`__init__.py`, `__main__.py`) | Encaminhador direto para `polaris.cli:main` criado durante a renomeação do produto. | **ARCHIVE** | Manter em modo deprecado até emissão formal de warning e remoção na v1.0. |

---

### 2. Benchmarks e Runners Antigos Substituídos

| Runner / Script | Propósito Original | Situação Atual | Classificação | Recomendação |
| :--- | :--- | :--- | :--- | :--- |
| `evaluations/goal24_runner.py` / `goal24_holdout_runner.py` | Execução de benchmarks específicos do GOAL 24 | Substituídos pelos benchmarks unificados offline (GOALS 28-30 e GOAL 39). | **ARCHIVE** | Mover para `evaluations/archive/goal24/` para não poluir a raiz de `evaluations/`. |
| `evaluations/goal25_runner.py` | Validação independente com NVIDIA A/B | Histórico do GOAL 25. Não utilizado na operação offline diária. | **ARCHIVE** | Mover para `evaluations/archive/goal25/`. |
| `evaluations/goal26_*.py` (4 scripts) | Tokenização MiniMax, pareamento e auditoria GOAL 26 | Concluído e arquivado. O GOAL 26 já possui relatórios consolidados. | **ARCHIVE** | Mover para `evaluations/archive/goal26/`. |
| `evaluations/goal27_runner.py` | Runner do experimento congelado GOAL 27 | O GOAL 27 está CONGELADO por diretriz contratual. O runner não deve ser executado. | **PROTECTED / ARCHIVE** | Manter estritamente como referência histórica de auditoria, sem execução. |
| `evaluations/goal28_offline_benchmark.py` | Benchmark inicial offline | Substituído pelo `goal39_benchmark.py` (5 domínios). | **ARCHIVE** | Manter como referência arquivada. |
| `evaluations/goal30_adversarial_benchmark.py` | Benchmark adversarial do GOAL 30 | Integrado conceitualmente ao benchmark completo do GOAL 39. | **KEEP** | Manter como suíte adversarial secundária rápida. |
| `evaluations/goal39_benchmark.py` | Benchmark abrangente de 5 domínios com economia de tokens | Runner canônico do estado atual. | **KEEP** | Padrão oficial de avaliação da plataforma. |

---

### 3. Redundância em Testes Automatizados

| Agrupamento de Testes | Quantidade | Diagnóstico | Classificação | Recomendação |
| :--- | :--- | :--- | :--- | :--- |
| `tests/test_goal24_*.py` | 11 arquivos | Testam variações pontuais de regras e filtros do GOAL 24. | **REFACTOR** | Consolidar os 11 arquivos em 2 arquivos organizados (`test_rules_catalog.py` e `test_benchmark_holdout.py`), reduzindo boilerplate de setup. |
| `tests/test_goal26_*.py` | 5 arquivos | Testes de integridade do pipeline pareado antigo. | **KEEP** | Manter para garantir não-regressão de cálculo de tokens. |
| `tests/test_context_*.py` | 8 arquivos | Testes fragmentados de ranqueamento de contexto AST. | **REFACTOR** | Consolidar testes unitários sobre a mesma classe para acelerar a inicialização do pytest. |

---

### 4. Relatórios Históricos no Fluxo Ativo (`evaluations/reports/`)

Atualmente existem **113 arquivos** em `evaluations/reports/`, cobrindo de forma granular todos os GOALS desde o GOAL 04.

- **Diagnóstico:** A raiz de relatórios está sobrecarregada, tornando a navegação humana e a indexação de ferramentas mais lenta.
- **Classificação:**
  - `evaluations/reports/legacy/` (**ARCHIVE**): Mover relatórios do GOAL 04 ao GOAL 23 (48 relatórios antigos).
  - `evaluations/reports/eval_runs/` (**ARCHIVE**): Mover arquivos JSON de execuções passadas (`goal28_offline_benchmark.json`, etc.).
  - `evaluations/reports/current/` (**KEEP**): Manter na raiz de reports apenas as matrizes consolidadas (`MASTER31_40_*`, `GOAL30_*`, `GOAL39_*` e `GOAL27_*`).

---

### 5. Resumo do Segundo Manifest Estrutural

| Ação Proposta | Módulos / Arquivos Envolvidos | Risco | Ganho de Engenharia |
| :--- | :--- | :--- | :--- |
| **KEEP** | `src/polaris/`, `tests/` novos, `evaluations/goal39_benchmark.py`, dados congelados GOAL 27 | Crítico | Mantém 100% da funcionalidade e validação offline. |
| **REFACTOR** | Unificação de sufixos `_3` em `orchestrator`, `context_ranker`, `behavioral_delta` | Médio | Elimina duplicação semântica e simplifica o grafo de importações. |
| **ARCHIVE** | Scripts de runners legados em `evaluations/` (GOALS 24, 25, 26, 28) | Baixo | Isola runners obsoletos em subpasta arquivada sem removê-los do git. |
| **ARCHIVE** | Subdiretório `evaluations/reports/legacy/` para GOALS 04-23 | Zero | Limpeza visual imediata de 48 arquivos de relatórios históricos. |
| **DELETE_CANDIDATE** | Nenhum novo arquivo marcado para deleção sem autorização posterior | Zero | Preservação absoluta do código. |
