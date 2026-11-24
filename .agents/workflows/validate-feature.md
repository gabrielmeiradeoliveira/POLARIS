# Workflow: validate-feature

## Objetivo
Comprovar por meio de evidências reais que uma funcionalidade atende integralmente aos seus critérios de aceitação.

## Pré-requisitos
- Funcionalidade no estado `IMPLEMENTED`.

## Documentos Obrigatórios
1. `vault/06-Quality/Validation-Strategy.md`
2. `vault/06-Quality/Evidence-Policy.md`
3. `vault/06-Quality/Definition-of-Done.md`

## Etapas
1. Conferir os critérios de aceitação definidos.
2. Preparar ambiente real ou representativo (sem mocks para comprovar integração).
3. Executar os comandos e testes de validação.
4. Coletar saídas reais, métricas e artefatos produzidos.
5. Registrar o relatório em `vault/09-Validation/Reports/` e evidências em `vault/09-Validation/Evidence/`.
6. Atualizar o estado para `VALIDATED` ou `FAILED`.

## Restrições
- Não fabricar logs, métricas ou resultados.
- Não considerar `IMPLEMENTED` como `VALIDATED`.

## Critérios de Aceitação
- Todos os critérios de aceitação comprovados com evidências rastreáveis.

## Evidências Exigidas
- Relatório completo seguindo `.agents/templates/validation-report.md`.

## Condições de Bloqueio
- Ambiente indisponível ou falha em qualquer critério obrigatório.
