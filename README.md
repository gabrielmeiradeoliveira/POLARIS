# POLARIS v3.2.1

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
- **v3.2.1:** Governança de sincronização `README.md`/`CHANGELOG.md` no `AGENTS.md` e atualização do `README.md`.
- **v3.2.0:** Página **Pull Requests** (`/#/pull-requests`) e endpoint `POST /api/prs/{pr_key}/ai-summary` com resumo executivo sob clique.
- **v3.1.1:** Inventário dinâmico de analisadores em `GET /api/meta` e na `StatusPage`.
- **v3.1.0:** UI Cockpit 3 Colunas, `IssueAiAssistant` no drawer de `Findings`, `VERSION` centralizado e `listen_addresses='*'` no PostgreSQL 17.
- **v3.0.0:** Camada de IA agnóstica (`/v1/chat/completions`) com calibração adaptativa (`500` moderno / `1200` legado) e cache por fingerprint.
- **v2.0.0:** Motor determinístico multi-linguagem, Quality Gates e persistência PostgreSQL 17.
