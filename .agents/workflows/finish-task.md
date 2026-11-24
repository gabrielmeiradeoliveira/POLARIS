# Workflow: finish-task

## Objetivo
Encerrar uma tarefa garantindo que testes, validação real, evidências e documentação estejam completos e sincronizados.

## Pré-requisitos
- Implementação ou alteração concluída.

## Documentos Obrigatórios
1. `vault/06-Quality/Definition-of-Done.md`
2. `vault/06-Quality/Evidence-Policy.md`
3. `vault/01-Project/Current-State.md`
4. `vault/11-History/Development-Log.md`

## Etapas
1. Verificar todos os itens aplicáveis da Definition of Done.
2. Executar testes e validações reais.
3. Registrar evidências reais em `vault/09-Validation/`.
4. Atualizar `vault/01-Project/Current-State.md`, `vault/11-History/Development-Log.md` e documentos afetados.
5. Verificar que não há arquivos temporários ou segredos expostos.
6. Entregar relatório final objetivo.

## Restrições
- Não declarar sucesso sem evidências.
- Não realizar commit ou push sem autorização.

## Critérios de Aceitação
- Todos os critérios da tarefa atendidos e documentados com evidências.

## Evidências Exigidas
- Comandos executados, saídas reais, status dos testes e arquivos atualizados.

## Condições de Bloqueio
- Falha em testes ou critérios de aceitação.
- Evidências ausentes ou inconsistentes.
