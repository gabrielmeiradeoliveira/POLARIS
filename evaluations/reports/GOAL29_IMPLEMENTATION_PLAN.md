# POLARIS — GOAL 29.1: Plano Geral de Implementação das 12 Fases

> **Documento:** `GOAL29_IMPLEMENTATION_PLAN.md`

---

## Estrutura Sequencial de Execução

- **Fase 29.1 — Baseline & Risk Register:** [CONCLUÍDA] Execução da suíte completa de 515 testes e catalogação de riscos.
- **Fase 29.2 — Budget & Quota Hardening:** Robustez atômica em concorrência, respostas sem usage, timeouts pós-envio e reconciliação conservadora.
- **Fase 29.3 — Behavioral Delta & ContextRanker Integration:** Arm ON alimentado pelo `ContextRanker` real (ranking estrutural, AST callers/callees, desempate determinístico).
- **Fase 29.4 — Security Guardrails 2.0:** Novas regras AST (remoção de verificações, inversão de predicados, fallback permissivo, supressão de exceções).
- **Fase 29.5 — Cross-File Contract Intelligence 2.0:** Suporte a tuplas, listas, TypedDict, dataclasses e assinaturas com argumentos obrigatórios/defaults.
- **Fase 29.6 — Evidence Registry & Arbitration 2.0:** Identidade canônica invariante a ordem, desduplicação por símbolo/causa e preservação de proveniência.
- **Fase 29.7 — Hybrid Orchestrator 2.0:** Pipeline fim a fim integrando AST, Guardrails, Contratos, ContextRanker e Arbitragem com tolerância a falhas parciais.
- **Fase 29.8 — CLI & JSON Observability:** Telemetria estruturada serializada no `AnalysisReport` e opções da CLI.
- **Fase 29.9 — Adversarial Offline Benchmark:** Dataset sintético com 20 casos adversariais (segurança, contratos, falsos positivos e refatorações).
- **Fase 29.10 — Performance & Stress Testing:** Testes de stress em repositórios sintéticos com grafos cíclicos e arquivos grandes.
- **Fase 29.11 — Packaging & Portability:** Compatibilidade multiplataforma, caminhos Unicode e execução sem dependência de rede.
- **Fase 29.12 — Final Acceptance:** Execução da suíte completa sem filtros, verificação SHA-256 do GOAL 27 e relatório final consolidado.
