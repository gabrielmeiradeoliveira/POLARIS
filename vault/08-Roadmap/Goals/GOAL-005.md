---
id: GOAL-005
title: Saneamento de Governança, Aprovação de ADRs e Fechamento de Paridade
status: COMPLETED
priority: CRITICAL
blocking: GOAL-004
version_target: 0.0.1-gov
created: 2026-11-17
updated: 2026-11-17
owner: project
tags:
  - goal
  - governance
  - adr
  - sonarqube-parity
---

# GOAL-005 — Saneamento de Governança, Aprovação de ADRs e Fechamento de Paridade

## 1. Objetivo
Resolver todas as pendências formais de arquitetura, produto e governança acumuladas antes da expansão do código do núcleo (`GOAL-004-B`), garantindo que o contrato de análise, a arquitetura do servidor e a linha de base de paridade com o SonarQube estejam congelados e formalmente aprovados.

## 2. Contexto e Justificativa
Atualmente, o projeto encontra-se na versão `0.0.0` com o `GOAL-004` em andamento (`IN_PROGRESS`), porém com cinco decisões arquiteturais estruturantes (`ADR-007` a `ADR-011`) ainda no estado `PROPOSED` e sem a definição formal da edição comercial de referência do SonarQube. Avançar na implementação do Scanner e do Server sem fechar esses artefatos gera risco direto de retrabalho no esquema relacional e no protocolo de comunicação entre processos.

## 3. Escopo de Entregas (Deliverables)

### 3.1. Formalização das Decisões Arquiteturais (ADRs)
Revisar, complementar (se necessário) e alterar o status de `PROPOSED` para `ACCEPTED` nos seguintes documentos em `vault/03-Architecture/ADR/`:
- [x] **ADR-007:** Adoção de Monólito Modular no POLARIS Server.
- [x] **ADR-008:** Separação física e lógica entre Scanner (CLI) e Server (API/Persistência).
- [x] **ADR-009:** Isolamento de analisadores especializados por linguagem via subprocesso.
- [x] **ADR-010:** Definição e congelamento do Contrato de Análise Versionado (schema JSON/Pydantic v1).
- [x] **ADR-011:** Modelo de persistência relacional (PostgreSQL 17).

### 3.2. Fechamento da Linha de Base de Produto
- [x] **Definição de Paridade SonarQube:** Formalizar em `vault/02-Product/SonarQube-Parity.md` a edição comercial de referência (ex.: *Developer Edition*) e delimitar o escopo exato de métricas, severidades e tipos de issues suportados na V2.x para Python, C# / .NET, Java e SQL.

### 3.3. Atualização de Rastreabilidade do Vault
- [x] Atualizar `vault/03-Architecture/ADR/Index.md` refletindo os novos status `ACCEPTED`.
- [x] Registrar as aprovações em `vault/11-History/Decision-Log.md`.
- [x] Atualizar `vault/08-Roadmap/Goals/Index.md` e `vault/01-Project/Current-State.md` vinculando o `GOAL-005` como pré-requisito concluído para a retomada do `GOAL-004-B`.

## 4. Critérios de Aceitação (Definition of Done)
De acordo com `vault/06-Quality/Definition-of-Done.md`:
1. Todos os documentos `ADR-007` a `ADR-011` possuem contexto, decisão, consequências e status `ACCEPTED` preenchidos.
2. O schema inicial do Contrato de Análise (`ADR-010`) está documentado sem ambiguidades de campos obrigatórios.
3. O documento `SonarQube-Parity.md` declara explicitamente a edição de referência sem pendências em aberto.
4. Nenhuma alteração de código de aplicação foi introduzida neste GOAL (escopo estritamente documental e de governança).

## 5. Impacto no Roadmap
- **Bloqueia:** Conclusão do `GOAL-004` (`GOAL-004-B`).
- **Desbloqueia:** Implementação segura da API v1, persistência no PostgreSQL 17 e integração do pipeline de subprocessos do Scanner.
