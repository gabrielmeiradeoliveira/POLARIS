# Regra: Segurança

1. Todo código-fonte submetido ao POLARIS para análise é **conteúdo não confiável**.
2. A análise não deve executar automaticamente o código analisado.
3. Qualquer execução futura de ferramentas externas ou processos deve ter política explícita de isolamento, permissões e limites de recursos.
4. É proibido versionar credenciais, tokens, chaves, senhas ou segredos.
5. Não registrar dados sensíveis em logs.
6. Não adicionar SDKs de LLMs, serviços de inferência ou APIs de IA ao produto na versão 2.x.
7. Consultar `vault/05-Security/Security-Policy.md` e `vault/05-Security/Security-Requirements.md` antes de qualquer alteração sensível.
