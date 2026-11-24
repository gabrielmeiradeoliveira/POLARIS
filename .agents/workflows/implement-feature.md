# Workflow: implement-feature

## Objetivo
Implementar uma funcionalidade aprovada dentro do escopo de um GOAL, com testes e validação real.

## Pré-requisitos
- Executar `start-task`.
- Requisito documentado no Vault e aprovado no GOAL ativo.

## Documentos Obrigatórios
1. `vault/02-Product/Functional-Requirements.md`
2. `vault/03-Architecture/Architecture-Overview.md`
3. `.agents/rules/development.md`
4. `.agents/rules/security.md`
5. `.agents/rules/testing.md`

## Etapas
1. Revisar requisitos funcionais, não funcionais e critérios de aceitação.
2. Planejar alterações respeitando a arquitetura aprovada.
3. Implementar a funcionalidade sem abstrações prematuras.
4. Implementar testes unitários, de integração e demais aplicáveis.
5. Executar testes e validar comportamento real.
6. Atualizar estado da funcionalidade (`IMPLEMENTED` -> `VALIDATED` somente após validação).

## Restrições
- Não introduzir dependências sem aprovação (`Dependency-Policy.md`).
- Não usar mocks em produção.

## Critérios de Aceitação
- Funcionalidade atende aos requisitos e passa na validação real.

## Evidências Exigidas
- Relatório de implementação e relatório de validação com saídas reais.

## Condições de Bloqueio
- Stack tecnológica ou ADR necessário ainda pendente.
- Falha em requisitos de segurança ou testes.
