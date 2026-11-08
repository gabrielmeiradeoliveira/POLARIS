# POLARIS — GOAL 28: Plano Detalhado de Implementação e Fases

> **Status:** Fase 28.1 — Auditoria e Planejamento  
> **Estratégia:** Implementação modular incremental, test-driven e offline-first.

---

## 1. Fases de Execução

### Fase 28.1 — Auditoria e Desenho Técnico (Concluída nesta etapa)
- **Atividades:**
  - Inspeção das estruturas existentes em `src/polaris/core/models.py`, `src/polaris/context/`, `src/polaris/intelligence/` e `src/polaris/modules/deterministic_rules.py`.
  - Isolamento da branch `feat/goal28-hybrid-engine`.
  - Elaboração dos documentos `GOAL28_ARCHITECTURE.md` e `GOAL28_IMPLEMENTATION_PLAN.md`.
- **Critério de Saída:** Arquitetura aprovada pelo usuário antes de qualquer código de produção.

---

### Fase 28.2 — Security Guardrail Engine (`polaris.guardrails`)
- **Arquivos a Criar:**
  - `src/polaris/guardrails/__init__.py`
  - `src/polaris/guardrails/models.py`
  - `src/polaris/guardrails/authorization.py`
  - `src/polaris/guardrails/engine.py`
  - `tests/test_guardrails.py`
- **Comportamentos a Implementar:**
  - Análise AST comparativa de antes/depois de funções de controle de acesso.
  - Detecção precisa do padrão do Caso 11 (`deny-by-default` para `allow-by-default`, aceite de `None`).
  - Níveis de evidência: `confirmed`, `suspected`, `unknown`.
  - Verificação de que alterações restritivas não geram falsos alarmes.
- **Testes Obrigatórios:**
  - Teste unitário reproduzindo o Caso 11 com fixture real.
  - Teste de negação de falsos positivos com nomes como "auth", "role", "security".

---

### Fase 28.3 — Cross-File Contract Analysis (`polaris.contracts`)
- **Arquivos a Criar:**
  - `src/polaris/contracts/__init__.py`
  - `src/polaris/contracts/models.py`
  - `src/polaris/contracts/consumer_tracker.py`
  - `src/polaris/contracts/engine.py`
  - `tests/test_contract_analysis.py`
- **Comportamentos a Implementar:**
  - Análise interprocedural de assinaturas de retorno e consumidores de propriedades/chaves.
  - Rastreamento da cadeia do Caso 9 (`encode()` -> intermediário -> consumidor `["value"]`).
  - Detecção de ciclos e limites de profundidade (max depth = 4, max nodes = 50).
- **Testes Obrigatórios:**
  - Reprodução do Caso 9 entre 3 arquivos sintéticos.
  - Tratamento de grafos cíclicos sem estouro de pilha.

---

### Fase 28.4 — Finding Arbitration Engine & Evidence Registry (`polaris.intelligence.arbitration`)
- **Arquivos a Criar:**
  - `src/polaris/intelligence/arbitration.py`
  - `src/polaris/intelligence/evidence_registry.py`
  - `tests/test_finding_arbitration.py`
- **Comportamentos a Implementar:**
  - Regra de inviolabilidade de segurança (guardrail `confirmed` nunca é suprimido).
  - Regra de refinamento de categoria (Caso 5: absorve categoria do ON sem duplicar).
  - Regra de preservação sob divergência (Caso 11: mantém alerta com status explícito).
  - Tolerância a falhas parciais (erros no ON preservam OFF).
- **Testes Obrigatórios:**
  - Simulação combinada dos Casos 5, 9 e 11.
  - Validação de idempotência e determinismo.

---

### Fase 28.5 — Hybrid Review Orchestrator (`polaris.review`)
- **Arquivos a Criar:**
  - `src/polaris/review/__init__.py`
  - `src/polaris/review/models.py`
  - `src/polaris/review/engine.py`
  - `tests/test_hybrid_orchestrator.py`
- **Comportamentos a Implementar:**
  - Orquestração de estágios: Estático -> Arm OFF -> Política de Expansão -> Arm ON (condicional) -> Arbitragem.
  - Respeito a orçamento de tokens e timeouts.
  - Suporte completo a `FakeProvider` para execução 100% offline.

---

### Fase 28.6 — Integração CLI, Validação e Relatório
- **Arquivos a Modificar/Criar:**
  - `src/polaris/cli.py` (Adição opt-in de `--strategy hybrid`)
  - `evaluations/reports/GOAL28_VALIDATION_REPORT.md`
- **Comportamentos a Implementar:**
  - Adição da opção sem alterar o comportamento padrão de `--strategy direct` / CLI atual.
  - Execução da suíte completa de testes de regressão (garantindo 0 falhas).
