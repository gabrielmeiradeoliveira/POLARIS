# Changelog

Todas as mudanças relevantes do projeto POLARIS serão documentadas neste arquivo.

## [3.7.3] - 2026-11-26

### Adicionado
- Ancoragem contextual profunda da IA (`IssueAiAssistant`) por `rule_id`, `cwe`, `file_path`, `start_line` e `code_snippet` com visualização comparativa Antes → Depois.
- Faixa de telemetria Delta do PR em `PullRequestsPage` com cálculo real de novos achados e achados resolvidos.
- Snippet de código real alimentado no `CodeEvidenceBlock` a partir dos metadados dos analisadores.
- Layout topo fixo com scroll interno desacoplado no `CockpitPage`.
- Padronização de espaçamento interno (`padding: 24px 32px`) em todas as páginas secundárias.
- Topbar contextual sincronizada com a rota ativa e dados do projeto/PR.

## [3.7.2] - 2026-11-26

### Adicionado
- Redesign "Aikido Security × Attio": Light Mode padrão arejado e Dark Mode grafite suave com tokens refinados.
- 4 gráficos SVG nativos com precisão matemática: `NoiseReductionFunnel`, `PostureTrendChart`, `FinOpsComparisonChart` e `TaintTrail`.
- Divulgação progressiva com 4 sinais técnicos e agrupamento inteligente `×N` salvo em `sessionStorage`.
- Fluxo contínuo Master-Detail com primeiro achado pré-selecionado, deep linking com reflexão na URL e navegação fluida em `#/cockpit`.

## [3.7.1] - 2026-11-26

### Adicionado
- Redesign estrutural "Code-First Telemetry Console": grade full-bleed com bordas sutis de `1px` e cabeçalho ultra-compacto de `44px`.
- Régua Contínua de Postura & Severidade e Mapa de Calor de Risco por Arquivo no `DashboardPage`.
- `<CodeEvidenceBlock />` com numeração de linha e destaque visual para evidências de código.
- `<TaintTrail />` integrado com atalhos de teclado de engenharia (`J`, `K`, `F`, `A`, `R`, `Esc`) no fluxo Master-Detail.
- Marcador ativo de `2px` em Polar Cyan na sidebar do `AppLayout`.
- Micro-telemetria FinOps compacta em linha única na página de Pull Requests.

## [3.7.0] - 2026-11-26

### Adicionado
- Design System polido Night Sky Slate (`#0B0D13` / `#111520` / `#1A2030`) com realces funcionais Polar Cyan (`#00F2FE` / `#4FACFE`).
- Eliminação total de termos genéricos/AI slop em favor de tipografia editorial densa, sóbria e técnica.
- Componente `TaintTrail` com renderização visual da esteira `SOURCE -> PROPAGATION -> SINK`.
- Fluxo contínuo Master-Detail e drawer responsivo integrado em `IssuesPage` e `PullRequestsPage`.
- Micro-telemetria técnica tabular com fontes monoespaçadas alinhadas e hierarquia visual rigorosa.

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
