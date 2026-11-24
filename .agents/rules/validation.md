# Regra: Validação

1. Seguir `vault/06-Quality/Validation-Strategy.md`, `vault/06-Quality/Definition-of-Done.md` e `vault/06-Quality/Evidence-Policy.md`.
2. Uma funcionalidade só recebe o estado `VALIDATED` após atendimento comprovado de todos os critérios de aceitação com evidências reais.
3. `IMPLEMENTED` não significa `VALIDATED`.
4. Não declarar sucesso sem evidências reais (comandos executados, saídas observadas, testes aprovados/reprovados, ambiente e limitações).
5. Nunca fabricar logs, métricas, resultados ou evidências.
6. Não alterar critérios de aceitação para acomodar falhas.
7. Um teste aprovado não implica aprovação integral de um GOAL; validação documental não comprova funcionamento do produto; build aprovado não comprova runtime; código experimental não equivale a código definitivo.
8. Evidências históricas são imutáveis e não podem ser apagadas ou modificadas retroativamente.
