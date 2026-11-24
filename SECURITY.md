# Política de Segurança — POLARIS

## Princípios Fundamentais

1. **Código Analisado é Não Confiável:** Todo código-fonte submetido ao POLARIS para análise deve ser tratado como entrada não confiável. O motor de análise não deve executar automaticamente o código analisado.
2. **Proibição de Segredos Versionados:** Nunca commitar senhas, tokens, chaves de API, certificados ou credenciais no repositório.
3. **Menor Privilégio:** Processos e ferramentas externas futuras devem operar com o mínimo de privilégios necessários e isolamento adequado.
4. **Sem IA na Versão 2.x:** Não é permitido adicionar SDKs de LLMs, serviços de inferência ou integrações externas de IA ao produto na versão 2.x.

## Documentação Detalhada

Consulte os documentos oficiais de segurança no Vault:
- `vault/05-Security/Security-Policy.md`
- `vault/05-Security/Security-Requirements.md`
- `vault/05-Security/Secrets-Management.md`
- `vault/05-Security/Dependency-Security.md`

## Reporte de Vulnerabilidades

Caso identifique uma vulnerabilidade de segurança neste repositório, não abra uma issue pública. Registre e comunique diretamente aos responsáveis pelo projeto.
