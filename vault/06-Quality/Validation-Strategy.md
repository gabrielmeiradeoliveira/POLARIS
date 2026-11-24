---
id: DOC-023
title: Estratégia de Validação Real
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: qa
tags:
  - polaris
  - quality
  - validation
---

# Estratégia de Validação Real

Uma funcionalidade **não** é considerada concluída apenas porque o código foi escrito, compilou, passou em teste unitário ou teve documentação escrita.

## Estados das Funcionalidades

```text
PLANNED
IN_PROGRESS
IMPLEMENTED
VALIDATED
BLOCKED
FAILED
```

`IMPLEMENTED` não significa `VALIDATED`. Somente funcionalidades que atenderem a todos os critérios de aceitação verificáveis com evidências reais recebem o estado `VALIDATED`.

## Regra Sobre Mocks

- Mocks não comprovam integração real.
- Dados simulados não comprovam persistência real.
- Respostas estáticas não comprovam funcionamento de APIs.
- A validação final deve utilizar componentes reais ou ambientes representativos devidamente identificados.
