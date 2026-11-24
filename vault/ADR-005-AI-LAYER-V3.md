---
id: ADR-005-AI-LAYER-V3
title: ADR-005 — Camada de Inteligência Artificial Cirúrgica (v3.0 & v3.0.2)
status: ACCEPTED
created: 2026-11-24
owner: project
tags:
  - adr
  - ai-layer
  - v3.0
  - v3.0.2
---

# ADR-005 — Camada de Inteligência Artificial Cirúrgica (`v3.0` & `v3.0.2`)

## 1. Princípio Arquitetural
- **Zero envio de repositório inteiro ao LLM:** A IA atua estritamente como camada cirúrgica pós-scan sobre candidatos filtrados pelo motor determinístico.
- **Cliente HTTP leve:** Sem SDKs pesados, compatível com provedores Cloud (Gemini, OpenAI, Anthropic) e locais (Ollama), preservando o teto de memória (`~93 MiB` RAM).

## 2. Casos de Uso `v3.0` (AI Core)
- **AI Triage Gate:** Análise semântica de candidatos `BLOCKER`/`CRITICAL` e `MEDIUM` recebendo apenas o recorte `SOURCE -> PROPAGATION -> SINK` (`±8 linhas` por passo) para classificar `CONFIRMED_EXPLOITABLE`, `LIKELY_FALSE_POSITIVE` ou `NEEDS_HUMAN_REVIEW`.
- **Closed-Loop Auto-Fix:** Geração sob demanda de diff unificado (`git apply`) com **revalidação obrigatória in-memory** pelo analisador determinístico do POLARIS antes de exibir o patch ao desenvolvedor.
- **Cache Persistente por Fingerprint:** Tabela/coluna no PostgreSQL indexada por `(fingerprint, snippet_hash, model_version)` para reutilizar análises sem gastar tokens em commits repetidos.

## 3. Escopo `v3.0.2` (Governança & Economia de Tokens)
- **Token Budget & Rate Limit:** Orçamento configurável por projeto/PR com priorização automática de `New Code` crítico.
- **Feedback Loop de Triagem:** Sanitizadores aprovados/rejeitados registrados no perfil do projeto.
- **Automação de PR:** Resumo consolidado de segurança e diffs sugeridos publicados automaticamente em Pull Requests do GitHub.
