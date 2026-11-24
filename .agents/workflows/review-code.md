# Workflow: review-code

## Objetivo
Revisar alterações de código e documentação quanto à conformidade arquitetural, qualidade, segurança e escopo.

## Pré-requisitos
- Alterações implementadas e prontas para revisão.

## Documentos Obrigatórios
1. `vault/04-Engineering/Code-Quality.md`
2. `vault/05-Security/Security-Policy.md`
3. `.agents/rules/architecture.md`
4. `.agents/rules/security.md`

## Etapas
1. Verificar aderência ao escopo do GOAL e aos requisitos.
2. Avaliar clareza, simplicidade e ausência de duplicação ou abstrações prematuras.
3. Verificar conformidade de segurança (entradas não confiáveis, segredos, logs).
4. Verificar cobertura de testes e ausência de mocks indevidos.
5. Verificar sincronização com a documentação do Vault.

## Restrições
- Não aprovar código sem evidência de testes executados.

## Critérios de Aceitação
- Ausência de violações críticas de segurança, arquitetura ou escopo.

## Evidências Exigidas
- Parecer técnico objetivo listando pontos verificados e eventuais pendências.

## Condições de Bloqueio
- Vulnerabilidade de segurança, violação de arquitetura ou falha em testes.
