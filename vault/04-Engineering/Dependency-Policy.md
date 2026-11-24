---
id: DOC-016
title: Política de Dependências
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: engineering
tags:
  - polaris
  - engineering
  - dependencies
---

# Política de Dependências

Nenhuma biblioteca ou dependência deve ser adicionada apenas por conveniência.

## Requisitos Obrigatórios por Dependência

Toda dependência relevante proposta para o projeto deve documentar:

1. **Justificativa técnica:** Por que é necessária.
2. **Finalidade:** Onde e como será utilizada.
3. **Licença:** Compatibilidade com o projeto.
4. **Versão:** Versão específica ou faixa controlada.
5. **Alternativas consideradas:** Opções avaliadas, incluindo implementação própria.
6. **Impacto operacional:** Tamanho, tempo de build, runtime e superfície de ataque.
7. **Compatibilidade com a arquitetura:** Aderência aos princípios do POLARIS.
8. **Estratégia de atualização:** Como será mantida e atualizada com segurança.

## Restrições Vigentes

- Não instalar dependências de produção no `GOAL-000`.
- Proibido adicionar SDKs de LLMs ou APIs de IA na versão 2.x.
