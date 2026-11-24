---
id: AUDIT-RULE-VALIDATOR
title: Auditoria Adversarial do Validador de Regras — GOAL-020-R2
type: validation-report
status: COMPLETED
created_at: 2026-11-15
updated_at: 2026-11-15
tags: [audit, adversarial, rules, goal-020-r2]
---

# Auditoria Adversarial do Validador de Regras

## 1. Achado Principal da Auditoria

- **Explicação do tempo anterior (`1,5764s`):** Na primeira execução do `validate_rules.py`, os casos em `tests/fixtures/rules/` não continham o campo `"code"` e o validador comparava `expectedPositive` com `observedPositive` pré-registrado no JSON.
- **Correção aplicada:** `scripts/validation/validate_rules.py` foi atualizado para executar `analyze_python_file` e `analyze_sql_file` em código-fonte real sempre que o campo `"code"` estiver presente na fixture.

## 2. Teste de Mutação

- `tests/unit/test_mutation_audit.py`: `1/1 OK` — comprovou que a mutação de `_check_bare_except` em cópia isolada de `rules_engine.py` altera o resultado de detecção (`[]` em vez de issue).

## 3. Evidências Geradas

- `vault/09-Validation/Evidence/GOAL-020-R2/rule-metrics.json`: Métricas individuais (`TP`, `FP`, `TN`, `FN`, `Precision`, `Recall`, `F1`) para todas as `204` regras.
- **Limitação pendente:** A execução automática de código-fonte por fixture via subprocesso para `PolarisCSharpAnalyzer.dll` e `JavaRulesEngine.class` permanece pendente de integração direta no `validate_rules.py`.
