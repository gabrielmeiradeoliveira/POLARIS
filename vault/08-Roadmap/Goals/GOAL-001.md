---
id: GOAL-001
title: Especificação do produto e estudo de paridade funcional com SonarQube
status: active
version: 2
created: 2026-11-14
updated: 2026-11-14
owner: product
tags:
  - polaris
  - goal
  - goal-001
---

# GOAL-001 — Especificação do produto e estudo de paridade funcional com SonarQube

- **Identificador:** GOAL-001
- **Estado:** COMPLETED
- **Objetivo:** Realizar o estudo formal de paridade funcional com o SonarQube e especificar os requisitos funcionais e não funcionais do POLARIS 2.0.

## Contexto
Com a fundação documental estabelecida no `GOAL-000`, o próximo passo é estudar a documentação oficial do SonarQube (identificando edição e versão de referência) para detalhar `SonarQube-Parity.md`, `Product-Requirements.md`, `Functional-Requirements.md` e `Non-Functional-Requirements.md`.

## Escopo
- Definir edição e versão do SonarQube utilizadas como referência.
- Estudar as categorias listadas em `SonarQube-Parity.md`.
- Especificar requisitos funcionais e não funcionais do POLARIS 2.0.
- Definir critérios de aceitação iniciais por módulo funcional.

## Fora de Escopo
- Implementação de código de produto.
- Cópia de código proprietário, marcas ou materiais protegidos do SonarQube.

## Dependências
- Conclusão do `GOAL-000` e autorização explícita do responsável pelo projeto.

## Tarefas
- [x] Incorporar validador documental portátil (`scripts/validation/validate-docs.ps1`).
- [x] Definir edição/versão de referência do SonarQube.
- [x] Completar `SonarQube-Parity.md`.
- [x] Especificar `Functional-Requirements.md`, `Non-Functional-Requirements.md`, `User-Journeys.md` e `Traceability-Matrix.md`.
- [x] Atualizar `Product-Requirements.md`, `07-Languages/` e `Current-State.md`.

## Critérios de Aceitação
- [x] Matriz de paridade detalhada com referência oficial identificada.
- [x] Requisitos funcionais, não funcionais, jornadas e rastreabilidade documentados.

## Estratégia de Testes
Validação documental automatizada via `scripts/validation/validate-docs.ps1`.

## Evidências
Registradas em [VAL-GOAL-001.md](../../09-Validation/Reports/VAL-GOAL-001.md).

## Riscos
- Escopo excessivo na primeira versão; mitigado por priorização clara no backlog.

## Resultado Final
Concluído (`COMPLETED`) em `2026-11-14`.
