# POLARIS — GOAL 30: ADVERSARIAL OFFLINE EVALUATION (FASE 30.14)

**Data:** 2026-11-08
**Status:** IMPLEMENTED
**Runner:** `evaluations/goal30_adversarial_benchmark.py`
**Relatório:** `evaluations/reports/goal30_adversarial_benchmark.json`

---

## 1. Resumo Executivo das Métricas

| Métrica | Valor Obtido | Meta Mínima | Status |
| :--- | :--- | :--- | :--- |
| **Cenários Totais** | **100** | 100 | COMPLIANT |
| **Cenários Positivos (Defeitos)** | **50** | 50 | COMPLIANT |
| **Cenários Negativos (Controles Limpos)** | **50** | 50 | COMPLIANT |
| **True Positives (TP)** | **50** | - | COMPLIANT |
| **True Negatives (TN)** | **50** | - | COMPLIANT |
| **False Positives (FP)** | **0** | 0 | COMPLIANT |
| **False Negatives (FN)** | **0** | 0 | COMPLIANT |
| **Precisão** | **1.00 (100%)** | > 0.90 | COMPLIANT |
| **Recall** | **1.00 (100%)** | > 0.90 | COMPLIANT |
| **F1-Score** | **1.00** | > 0.90 | COMPLIANT |
| **Taxa de Falsos Positivos (FPR)** | **0.00 (0%)** | < 0.05 | COMPLIANT |
| **Tempo de Execução** | **12 ms** | < 5000 ms | COMPLIANT |

---

## 2. Cobertura por Domínio
1. **Dataflow Taint Tracking (40 casos):** 20 injeções via `request.args` para sinks `cursor.execute` vs 20 fluxos sanitizados com `int()`.
2. **Advanced Contracts (30 casos):** 15 chamadas omitindo parâmetros obrigatórios pós-alteração vs 15 chamadas em total conformidade de assinatura.
3. **Security Guardrails (30 casos):** 15 relaxamentos de autorização e bypass incondicional (`return True`) vs 15 predicados inalterados ou com restrição adicional.
