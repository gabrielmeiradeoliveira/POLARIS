# Workflow: fix-bug

## Objetivo
Diagnosticar, corrigir e validar a resolução de um defeito sem introduzir regressões.

## Pré-requisitos
- Descrição do problema ou evidência da falha.

## Documentos Obrigatórios
1. `vault/11-History/Known-Issues.md`
2. `.agents/rules/development.md`
3. `.agents/rules/testing.md`
4. `.agents/rules/validation.md`

## Etapas
1. Reproduzir o problema e coletar evidência inicial da falha.
2. Identificar a causa raiz.
3. Planejar a correção mínima necessária.
4. Implementar a correção e adicionar teste de regressão.
5. Executar a suíte de testes relevante e validar o comportamento real.
6. Atualizar `vault/11-History/Known-Issues.md` e `vault/11-History/Development-Log.md`.

## Restrições
- Não mascarar sintomas nem desabilitar testes.

## Critérios de Aceitação
- Bug não se reproduz e testes de regressão passam.

## Evidências Exigidas
- Evidência da falha antes da correção e evidência da correção após o ajuste.

## Condições de Bloqueio
- Incapacidade de reproduzir ou causa raiz dependente de decisão externa.
