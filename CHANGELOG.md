# Changelog

Todas as mudanças relevantes do projeto POLARIS serão documentadas neste arquivo.

## [3.6.0] - 2026-11-26

### Adicionado
- Triagem em Lote e Supressão Auditável de Vulnerabilidades via endpoint `PATCH /api/findings/batch-triage`.
- Fingerprint determinístico de findings imune a deslocamento de linha (`compute_finding_fingerprint` e migration `006_finding_triages.sql`).
- Otimização FinOps com filtragem e short-circuit no `/ai-summary`: findings suprimidos (`FALSE_POSITIVE`, `WONT_FIX`, etc.) não consomem tokens de LLM.
- UI completa de seleção múltipla em `IssuesPage` com `IndeterminateCheckbox`, modal de triagem e barra de ações flutuante grafite ardósia (`BatchTriageBar`).

## [3.5.1] - 2026-11-26

### Adicionado
- Cache persistente de resumos de PR em PostgreSQL (`ai_pr_summaries` e `SummaryCacheService`).
- Retorno de 5 métricas completas de tokens em `/ai-summary`: `estimated_tokens`, `actual_input_tokens`, `actual_output_tokens`, `actual_total_tokens` e `saved_tokens`.
- Alternador de tema visual Sol-Lua com botão acessível e estilo refinado em `AppLayout.tsx`.

### Corrigido
- `HTTP 500` (`NameError: os`) no endpoint `POST /api/prs/{pr_key}/ai-summary` ao processar resumos de PR.

## [0.0.0] - 2026-11-14

### Adicionado
- Estrutura inicial do repositório (GOAL-000).
- Contrato operacional `AGENTS.md`.
- Procedimentos e regras em `.agents/`.
- Base oficial de conhecimento em `vault/`.
- Políticas de segurança, qualidade, testes, validação e governança.
