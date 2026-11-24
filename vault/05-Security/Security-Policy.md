---
id: DOC-018
title: Política de Segurança
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: security
tags:
  - polaris
  - security
  - policy
---

# Política de Segurança

A segurança do POLARIS é obrigatória desde a fundação do projeto.

## Princípios

1. **Código Analisado é Não Confiável:** Todo código-fonte recebido pelo POLARIS é tratado como conteúdo não confiável e **não deve ser executado automaticamente**.
2. **Isolamento de Processos Futuros:** Qualquer execução futura de ferramentas externas, compiladores ou processos exigirá política explícita de isolamento, permissões mínimas e limites de recursos.
3. **Menor Privilégio:** Componentes e processos devem operar apenas com as permissões estritamente necessárias.
4. **Sem IA na V2.x:** Proibido incluir SDKs de LLMs, serviços de inferência ou APIs de IA no produto na versão 2.x.
