# POLARIS v3.7.3

Plataforma híbrida de análise estática (SAST, Taint Tracking e Qualidade de Código) com motor 100% determinístico no pipeline e camada de IA sob demanda (Ollama local ou Cloud agnóstico `/v1/chat/completions`).

## Linguagens & Motores Suportados
- **Core:** Python (`ast` + Taint Flow), C# / .NET (`Roslyn`), Java (`JavaParser`), SQL (`SQLGlot`)
- **Expansão Multi-Linguagem:** Terraform/HCL, TypeScript/React/JSX, HTML, PHP, Shell/Bash, Kotlin, Rust, C/C++

## Quickstart (Docker)
```bash
# Modo 100% Determinístico (api + postgres)
docker compose up -d --build

# Modo Híbrido com IA Local (api + postgres + ollama qwen2.5-coder:3b)
docker compose --profile ai up -d --build
```
Acesse a UI em `http://localhost:8000` (Pull Requests em `http://localhost:8000/#/pull-requests`).

## Histórico de Versões
- **v3.7.3:** Ancoragem real da IA por `rule_id`/`cwe`/`file_path`/`start_line`/`code_snippet` com comparativo Antes → Depois, faixa de Delta do PR na `PullRequestsPage`, `CodeEvidenceBlock` com snippet real, topo fixo sem scroll no `CockpitPage`, `padding: 24px 32px` nas páginas secundárias e topbar contextual sincronizada.
- **v3.7.2:** Redesign "Aikido Security × Attio": Light Mode padrão arejado + Dark grafite suave, 4 gráficos SVG nativos (`NoiseReductionFunnel`, `PostureTrendChart`, `FinOpsComparisonChart`, `TaintTrail`), divulgação progressiva com 4 sinais e agrupamento `×N` persistido em `sessionStorage`, Master-Detail contínuo com 1º achado pré-selecionado, deep links com atualização dinâmica de URL e rota `/cockpit`.
- **v3.7.1:** Redesign estrutural "Code-First Telemetry Console": grade full-bleed `1px`, header `44px`, Régua Contínua de Postura & Severidade + Mapa de Calor de Risco por Arquivo no Dashboard, `<CodeEvidenceBlock />` com numeração de linha + `<TaintTrail />` + atalhos `J`/`K`/`F`/`A`/`R`/`Esc` no Master-Detail, marcador `2px` Polar Cyan na sidebar e micro-telemetria FinOps em linha única no PR.
- **v3.7.0:** Polimento de Design System Night Sky Slate + Polar Cyan, eliminação total de AI slop, componente `TaintTrail` `SOURCE -> SINK`, fluxo contínuo Master-Detail em `IssuesPage` e `PullRequestsPage`, e micro-telemetria tabular/monoespaçada.
- **v3.6.0:** Triagem em Lote e Supressão Auditável (`PATCH /api/findings/batch-triage`), fingerprint determinístico imune a deslocamento de linha, migration `006_finding_triages.sql`, filtragem/short-circuit FinOps no `/ai-summary` e UI de seleção em lote com barra flutuante grafite ardósia (`BatchTriageBar.tsx`).
- **v3.5.1:** Correção do `/ai-summary` (`NameError: os`), cache persistente de resumos em PostgreSQL (`ai_pr_summaries`), telemetria completa com 5 métricas de tokens (`estimated_tokens`, `actual_input_tokens`, `actual_output_tokens`, `actual_total_tokens`, `saved_tokens`) e limpeza visual com alternador Sol-Lua refinado em `AppLayout.tsx`.
- **v3.5.0:** Logo SVG autoral de 12 pontas (`PolarisLogo.tsx`), paleta grafite ardósia sóbria (`#111317` / `#171A20` / `#4F6BED`) e limpeza da topbar.
- **v3.4.1:** Badge `ALIVE` verde em `StatusPage` e indicador `PostgreSQL Conectado` centralizado na página de Status.
- **v3.4.0:** Previsão determinística de tokens (`GET /api/ai/estimate`), telemetria `Previsto vs. Real`, contraste global de botões no modo escuro e painel estruturado de resumo em `PullRequestsPage`.
- **v3.3.0:** Rota `#/pull-requests` e item no menu lateral conectados; compactação determinística O(1) (`POLARIS_AI_PR_MAX_INPUT_CHARS=3500`, Top-5 riscos) para Mega-PRs (84k+ linhas).
- **v3.2.1:** Governança de sincronização `README.md`/`CHANGELOG.md` no `AGENTS.md` e atualização do `README.md`.
- **v3.2.0:** Página **Pull Requests** (`/#/pull-requests`) e endpoint `POST /api/prs/{pr_key}/ai-summary` com resumo executivo sob clique.
- **v3.1.1:** Inventário dinâmico de analisadores em `GET /api/meta` e na `StatusPage`.
- **v3.1.0:** UI Cockpit 3 Colunas, `IssueAiAssistant` no drawer de `Findings`, `VERSION` centralizado e `listen_addresses='*'` no PostgreSQL 17.
- **v3.0.0:** Camada de IA agnóstica (`/v1/chat/completions`) com calibração adaptativa (`500` moderno / `1200` legado) e cache por fingerprint.
- **v2.0.0:** Motor determinístico multi-linguagem, Quality Gates e persistência PostgreSQL 17.
