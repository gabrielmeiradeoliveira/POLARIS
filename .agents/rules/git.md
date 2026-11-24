# Regra: Git

1. Não realizar `git commit` ou `git push` sem autorização explícita do responsável pelo projeto.
2. Seguir a estratégia definida em `vault/04-Engineering/Git-Strategy.md`.
3. Nunca versionar segredos, credenciais, arquivos temporários ou artefatos locais ignorados em `.gitignore`.


## Padrão Obrigatório de Commits (Conventional Commits)

Todo commit deve seguir o formato:
`<tipo>(<escopo>): <descrição objetiva no imperativo>`

- **Tipos permitidos:** `feat`, `fix`, `perf`, `refactor`, `test`, `ci`, `docs`, `chore`.
- **Descreva O QUE mudou**, nunca apenas o número do GOAL ou da release.
- **Commits atômicos:** separar mudanças distintas em commits independentes por responsabilidade.
- **Referência ao GOAL (opcional):** colocar no corpo do commit (ex.: `Refs: GOAL-019`), nunca no título.
- **Tamanho do título:** máximo de 72 caracteres, em minúsculas após `:`, sem ponto final.
