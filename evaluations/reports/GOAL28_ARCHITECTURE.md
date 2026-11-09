# POLARIS — GOAL 28: Documento de Arquitetura e Especificação Técnica
## Hybrid Review Engine, Security Guardrails & Cross-File Contract Analysis

> **Status:** Fase 28.1 — Auditoria e Desenho Arquitetural
> **Modo:** Offline-first, determinístico, testável e estritamente opt-in
> **Branch de Trabalho:** `feat/goal28-hybrid-engine`
> **Isolamento:** Os artefatos e dados do GOAL 27 permanecem congelados e intocados.

---

## 1. Visão Geral e Motivação

O **GOAL 28** introduz a infraestrutura de revisão híbrida no POLARIS para superar os gargalos empíricos diagnosticados no benchmark do GOAL 27:

1. **Caso 5 (Classificação Incorreta sem Contexto):** O Arm OFF apontou `type_mismatch` (FP+FN), enquanto o Arm ON utilizou os chamadores para apontar com precisão `null_handling`. O novo motor deve integrar evidências de contratos e consumidores para refinar a categoria e severidade, sem duplicar findings.
2. **Caso 9 (Quebra Indireta de Contrato):** Uma alteração de contrato de retorno de dicionário para escalar atravessou componentes intermediários até quebrar o consumidor final `encoded["value"]`. Ambos os braços do LLM falharam. O novo analisador estático interprocedural deve rastrear cadeias de retorno/consumo com profundidade configurável e registrar evidências reproduzíveis.
3. **Caso 11 (Supressão de Vulnerabilidade de Autorização):** O Arm OFF identificou o relaxamento de autorização (`role is None or role == "admin"`), enquanto o Arm ON suprimiu o finding por dispersão de atenção (Attention Dilution). O novo Security Guardrail determinístico garante que evidências comprovadas de relaxamento de acesso nunca sejam silenciadas pela ausência de findings no LLM.

---

## 2. Topologia Arquitetural e Localização de Módulos

Para manter conformidade estrita com o layout de pacotes existente em `src/polaris/`, os novos componentes serão organizados modularmente:

```text
src/polaris/
├── guardrails/                          # MÓDULO A: Security Guardrail Engine
│   ├── __init__.py
│   ├── models.py                        # ConfidenceLevel, GuardrailEvidence, SecurityFinding
│   ├── authorization.py                 # Regras AST de relaxamento de autorização (Caso 11)
│   └── engine.py                        # Orquestrador determinístico de guardrails
│
├── contracts/                           # MÓDULO B: Cross-File Contract Analysis
│   ├── __init__.py
│   ├── models.py                        # ContractRelation, PropagationPath, IncompatibilityEvidence
│   ├── consumer_tracker.py              # Rastreador de acessos (dict keys, attributes)
│   └── engine.py                        # Propagação inter-arquivos limitada (Caso 9)
│
├── intelligence/
│   ├── evidence_registry.py             # MÓDULO E: Structured Evidence Registry
│   └── arbitration.py                   # MÓDULO D: Finding Arbitration Engine (Casos 5 e 11)
│
├── review/                              # MÓDULO C: Hybrid Review Orchestrator
│   ├── __init__.py
│   ├── models.py                        # ReviewStrategy, ExpansionPolicy, HybridReviewResult
│   └── engine.py                        # Orquestrador OFF-first com ON seletivo
│
└── cli.py                               # MÓDULO F: Opção --strategy hybrid (Opt-in)
```

---

## 3. Especificação dos Módulos

### 3.1. Módulo A — Security Guardrail Engine (`polaris.guardrails`)
- **Regras AST Determinísticas:**
  - `detect_authorization_relaxation`: Inspeciona funções com parâmetros de permissão/role ou predicados de autorização e detecta introdução de branches que aceitam `None` ou que tornam a negação permissiva (ex.: `role is None or ...`, `if not authorized` -> removido).
  - **Diferenciação Estrita de Confiança:**
    - `confirmed`: AST comprova formalmente o relaxamento da guarda dentro do escopo suportado.
    - `suspected`: Mudança em função sensível sem prova matemática completa.
    - `unknown`: Expressões dinâmicas ou limites estáticos excedidos.
  - **Invariante de Preservação:** Um finding `confirmed` gerado pelos guardrails recebe status de prioridade máxima e **não pode ser removido** mesmo que o Arm ON retorne lista vazia.

### 3.2. Módulo B — Cross-File Contract Analysis (`polaris.contracts`)
- **Rastreamento de Contrato Interprocedural Bounded:**
  - Extrai funções exportadas modificadas no diff (`git diff`).
  - Analisa o grafo de chamadas via AST (`polaris.context.python_ast` e `dependency_graph`).
  - Identifica se o valor de retorno mudou (ex.: de `dict` constante para parâmetro bruto `x`).
  - Propaga a referência ao longo dos arquivos importadores até identificar acessos incompatíveis (ex.: Subscript `["value"]`).
  - **Limites de Operação:** Profundidade máxima de 4 saltos, máximo de 50 nós, detecção de ciclos com corte, sem suposições agressivas quando tipos forem desconhecidos.

### 3.3. Módulo D — Finding Arbitration Engine (`polaris.intelligence.arbitration`)
- **Deduplicação Semântica e Resolução de Conflitos:**
  - **Agrupamento por Localização e Símbolo:** Conecta findings do Guardrail, Arm OFF e Arm ON que cobrem a mesma entidade.
  - **Regra 1 (Segurança Inviolável):** Finding de guardrail `confirmed` é promovido com status `confirmed`, independente do retorno do LLM.
  - **Regra 2 (Refinamento Taxonômico - Caso 5):** Se OFF emitiu `type_mismatch` e ON emitiu `null_handling` com evidência contextual no mesmo símbolo, a categoria do ON é adotada sem duplicar o finding, preservando a proveniência de ambas as fontes.
  - **Regra 3 (Supressão pelo Contexto - Caso 11):** Se OFF emitiu finding de segurança e ON retornou vazio, o finding é preservado com status `disputed_by_context` ou `confirmed` (se corroborado por guardrail), nunca descartado.
  - **Regra 4 (Falhas Operacionais):** Timeouts ou erros de rede no Arm ON marcam a revisão como `partially_completed`, mantendo 100% dos resultados válidos do OFF e dos guardrails.

### 3.4. Módulo C — Hybrid Review Orchestrator (`polaris.review.engine`)
- **Execução em Estágios (OFF-first com ON seletivo):**
  1. **Estágio 1:** Executa Guardrails e Análise de Contratos (0 chamadas LLM).
  2. **Estágio 2:** Executa Arm OFF (1 chamada LLM, diff puro).
  3. **Estágio 3 (Política de Expansão):** Avalia se necessita de Arm ON baseado em:
     - Quebra de contrato detectada pelo módulo B.
     - Finding do OFF com categoria dependente de contexto (`type_mismatch`, `null_handling`).
     - Alerta de guardrail necessitando de enriquecimento semântico.
  4. **Estágio 4:** Executa Arm ON apenas se a política exigir e houver orçamento/cota disponível.
  5. **Estágio 5:** Arbitra e consolida os findings com registro de proveniência no Evidence Registry.

---

## 4. Garantias e Mitigações de Riscos

1. **Isolamento Absoluto do GOAL 27:**
   - Nenhum arquivo de avaliação ou resultado do GOAL 27 é tocado.
   - Os testes existentes continuam rodando via mock/FakeProvider.
2. **Compatibilidade e Opt-in:**
   - A CLI padrão mantém seu comportamento inalterado.
   - A nova estratégia híbrida só é acionada quando o usuário passar `--strategy hybrid`.
3. **Determinismo e Modo Offline:**
   - Todo o pipeline funciona offline sem qualquer dependência externa ou consumo de cotas.
