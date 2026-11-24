---
id: DOC-007
title: Matriz de Paridade com SonarQube
status: active
version: 2
created: 2026-11-14
updated: 2026-11-17
owner: product
tags:
  - polaris
  - product
  - sonarqube
  - parity
---

# Matriz de Paridade com SonarQube

## 1. Pesquisa Oficial de Referência

- **Produto de Referência:** SonarQube Server **2026.5 LTA** & SonarQube Community Build
- **Edições Estudadas:** Community Build (open-source), Developer Edition, Enterprise Edition, Data Center Edition
- **Edição de Referência Alvo para Paridade Funcional (V2.x):** **SonarQube Developer Edition (2026.5 LTA)** (aprovada formalmente no `GOAL-005`), cobrindo os recursos do Community Build somados a análise de branches, pull requests e SQL (T-SQL / PL-SQL), excluindo portfólios/relatórios executivos Enterprise, clustering HA de Data Center e add-ons de IA.
- **Fontes Consultadas:** Documentação oficial da SonarSource (`https://docs.sonarsource.com/sonarqube-server/2026.5/` e páginas comparativas de edições em `sonarsource.com`).
- **Data da Consulta:** `2026-11-14`
- **Restrições de Licenciamento:** O POLARIS 2.0 é uma implementação limpa e independente; não copia código proprietário, marcas ou materiais protegidos do SonarQube.

## 2. Disponibilidade por Edição (Referência)

| Categoria | Community Build | Developer | Enterprise | Data Center |
| :--- | :---: | :---: | :---: | :---: |
| Análise da branch principal, Issues, Métricas, Quality Gates, Quality Profiles | Sim | Sim | Sim | Sim |
| Análise de Branches e Pull Requests | Não | Sim | Sim | Sim |
| Python, C#, Java | Sim | Sim | Sim | Sim |
| SQL (T-SQL / PL-SQL) | Não | Sim | Sim | Sim |
| Portfólios, Relatórios Executivos PDF, Processamento Paralelo | Não | Não | Sim | Sim |
| Alta Disponibilidade (HA) e Clustering | Não | Não | Não | Sim |
| Add-ons de IA (Remediation Agent, Vortex, Hunter) | Não | Não | Add-on pago | Add-on pago |

## 3. Matriz de Paridade Funcional do POLARIS 2.x

| ID Ref | Capacidade | Paridade Alvo POLARIS 2.x | Estado |
| :--- | :--- | :--- | :--- |
| `SQ-01` | Gerenciamento de projetos | Equivalência integral (local) | `PLANNED` |
| `SQ-02` | Scanner | Equivalência integral (CLI local) | `PLANNED` |
| `SQ-03` | Configuração de análises | Equivalência integral | `PLANNED` |
| `SQ-04` | Catálogo de regras | Equivalência para Python, C#, Java e SQL | `PLANNED` |
| `SQ-05` | Gerenciamento de issues | Equivalência integral | `PLANNED` |
| `SQ-06` | Métricas de qualidade | Equivalência integral | `PLANNED` |
| `SQ-07` | Complexidade | Equivalência integral | `PLANNED` |
| `SQ-08` | Duplicação de código | Equivalência integral | `PLANNED` |
| `SQ-09` | Cobertura de testes | Importação de relatórios padrão | `PLANNED` |
| `SQ-10` | Dívida técnica | Cálculo determinístico por regra | `PLANNED` |
| `SQ-11` | Quality Gates | Equivalência integral | `PLANNED` |
| `SQ-12` | Quality Profiles | Equivalência integral | `PLANNED` |
| `SQ-13` | Histórico de análises | Equivalência integral (snapshots locais) | `PLANNED` |
| `SQ-14` | Análise de código novo | Equivalência (Clean as You Code) | `PLANNED` |
| `SQ-15` | Branches | Equivalência local (rastreamento por branch) | `PLANNED` |
| `SQ-16` | Pull requests | Análise delta local / integração CI | `PLANNED` |
| `SQ-17` | Dashboard | Interface web local | `PLANNED` |
| `SQ-18` | Administração | Configurações locais da plataforma | `PLANNED` |
| `SQ-19` | Usuários e permissões | Controle de acesso local (RBAC básico) | `PLANNED` |
| `SQ-20` | API | API HTTP local documentada | `PLANNED` |
| `SQ-21` | Integrações CI/CD | Execução via CLI + saída padronizada | `PLANNED` |
| `SQ-22` | Instalação e operação | Instalação local determinística | `PLANNED` |

## 4. Escopo Delimitado para V2.x (Python, C# / .NET, Java e SQL)

- **Linguagens Suportadas:** Python (`3.12+`), C# / .NET (`Roslyn`), Java (`JavaParser`) e SQL (`SQLGlot` — T-SQL, PL/SQL e ANSI SQL).
- **Tipos de Issues:** `BUG`, `VULNERABILITY`, `CODE_SMELL` e `SECURITY_HOTSPOT`.
- **Severidades:** `BLOCKER`, `CRITICAL`, `MAJOR`, `MINOR`, `INFO`.
- **Métricas Base:** `ncloc` (linhas de código), `complexity` (ciclomática/cognitiva), `duplicated_lines_density`, `coverage` (via importação de relatórios padrão), `sqale_index` (dívida técnica determinística) e contagens de issues por tipo e severidade.
