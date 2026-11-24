---
id: DOC-022
title: Estratégia de Testes
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: qa
tags:
  - polaris
  - quality
  - testing
---

# Estratégia de Testes

> [!NOTE]
> Frameworks de teste definitivos não devem ser escolhidos antes da aprovação da stack tecnológica (`Technology-Stack.md`).

## Tipos de Teste Obrigatórios

1. **Testes Unitários:** Validar componentes individuais e comportamentos isolados. Mocks podem ser usados quando apropriado.
2. **Testes de Integração:** Validar a comunicação real entre componentes, sem substituir integrações reais por mocks.
3. **Testes End-to-End (E2E):** Validar funcionalidades completas do ponto de vista do usuário.
4. **Testes de Regressão:** Garantir que problemas corrigidos não reapareçam.
5. **Testes de Contrato:** Validar interfaces e formatos compartilhados entre componentes.
6. **Testes de Desempenho:** Medir tempo de execução, consumo de memória e comportamento sob diferentes volumes de código.
7. **Testes de Robustez:** Validar entradas inválidas, arquivos incompletos, falhas operacionais e situações inesperadas.
8. **Testes de Instalação:** Validar build, instalação, inicialização e execução em ambientes oficialmente suportados.
