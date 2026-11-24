---
id: DOC-054
title: Threat Model Inicial
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: security
tags:
  - polaris
  - architecture
  - threat-model
---

# Threat Model Inicial — POLARIS 2.0

## 1. Ativos, Atores e Fronteiras de Confiança

- **Ativos:** Código-fonte analisado, banco de dados de métricas/issues, tokens de análise, credenciais administrativas, integridade dos Quality Gates.
- **Atores:** Desenvolvedor, Administrador, Pipeline CI/CD, Repositório Não Confiável (atacante).
- **Fronteiras de Confiança:** (1) Repositório analisado -> Scanner/Analisadores; (2) Scanner -> API do Server; (3) Usuário/Browser -> Dashboard/API.

## 2. Matriz de Ameaças e Controles Propostos

| Ameaça | Superfície | Impacto | Controle Proposto | Teste de Segurança |
| :--- | :--- | :--- | :--- | :--- |
| Execução de código via repositório malicioso / MSBuild / Maven / Gradle | Scanner / Analisador | Crítico | Não executar código analisado; sandbox/isolamento, menor privilégio e bloqueio de rede se build for necessário | Teste com projeto contendo script malicioso |
| Path traversal e symlinks maliciosos | Scanner / Ingestão | Alto | Canonicalização de caminhos e bloqueio de leitura fora da raiz do projeto | Teste com `../` e symlinks apontando para fora |
| Exaustão de CPU/Memória (arquivos gigantes ou parser bombs) | Analisadores / API | Alto | Limites de tamanho de arquivo, timeout por arquivo/análise e limite de payload | Fuzzing e teste com arquivos de tamanho extremo |
| Injeção de comandos / SQL Injection / XSS | Scanner / API / UI | Crítico | Sem shell interpolation; queries parametrizadas; encoding/CSP no frontend | Testes de injeção e XSS na API/UI |
| Relatórios adulterados ou acesso entre projetos | API / Persistência | Alto | Autenticação por token, RBAC e filtro obrigatório por `projectId` | Teste de acesso cruzado (IDOR) |
| Vazamento de credenciais ou código-fonte | Logs / Persistência | Alto | Mascaramento em logs; não armazenar código-fonte integral sem necessidade | Inspeção de logs após falhas |
