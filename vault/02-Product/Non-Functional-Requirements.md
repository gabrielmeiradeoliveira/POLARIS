---
id: DOC-009
title: Requisitos Não Funcionais
status: active
version: 2
created: 2026-11-14
updated: 2026-11-14
owner: product
tags:
  - polaris
  - product
  - non-functional-requirements
---

# Requisitos Não Funcionais — POLARIS 2.0

Metas quantitativas ainda não fundamentadas por benchmarks permanecem explicitamente como **propostas pendentes** para definição após a escolha da stack tecnológica (`GOAL-002`).

| ID | Categoria | Requisito | Critério de Aceitação (`CA-NFR-XXX`) | Estado |
| :--- | :--- | :--- | :--- | :--- |
| `REQ-NFR-001` | Desempenho | O scanner e o servidor devem processar análises locais sem travamentos ou gargalos impeditivos. | Benchmarks definidos e medidos após `GOAL-002` (meta quantitativa pendente). | `PLANNED` |
| `REQ-NFR-002` | Consumo de Recursos | Operar dentro de limites razoáveis de CPU e memória em máquinas de desenvolvimento locais. | Consumo medido em testes de desempenho sem vazamento de memória (meta exata pendente). | `PLANNED` |
| `REQ-NFR-003` | Escalabilidade | Suportar crescimento gradual do número de arquivos e histórico de análises locais. | Testes com volumes crescentes de código executados sem degradação crítica. | `PLANNED` |
| `REQ-NFR-004` | Confiabilidade | Falhas em um arquivo não devem corromper o estado global do projeto ou banco de dados. | Transações atômicas e tratamento explícito de erros em análises parciais. | `PLANNED` |
| `REQ-NFR-005` | Reprodutibilidade | Mesma entrada, configuração e versão de regras devem produzir exatamente os mesmos resultados. | Duas execuções idênticas geram saída determinística idêntica. | `PLANNED` |
| `REQ-NFR-006` | Funcionamento Local | Toda a plataforma V2.x deve operar 100% localmente, sem dependência obrigatória de internet ou nuvem. | Execução completa validada em ambiente sem acesso à rede externa. | `PLANNED` |
| `REQ-NFR-007` | Portabilidade | Suportar execução nos sistemas operacionais alvo definidos na arquitetura. | Testes de instalação aprovados nos SOs oficialmente suportados. | `PLANNED` |
| `REQ-NFR-008` | Manutenibilidade | Arquitetura modular que permita adicionar regras e evoluir analisadores sem acoplamento excessivo. | Separação clara entre núcleo, analisadores, persistência e interface. | `PLANNED` |
| `REQ-NFR-009` | Observabilidade | Logs estruturados de execução, erros e auditoria sem exposição de segredos. | Logs permitem diagnosticar falhas sem vazar tokens ou credenciais. | `PLANNED` |
| `REQ-NFR-010` | Privacidade | Código-fonte analisado permanece exclusivamente local; zero telemetria oculta ou envio a APIs de IA. | Inspeção de rede confirma ausência de tráfego externo não autorizado. | `PLANNED` |
| `REQ-NFR-011` | Segurança Operacional | Código analisado é tratado como não confiável e nunca executado automaticamente; proteção contra path traversal e segredos. | Testes de segurança confirmam não execução de código e validação de caminhos. | `PLANNED` |
| `REQ-NFR-012` | Acessibilidade | Interface web local deve seguir boas práticas básicas de contraste, semântica e navegação por teclado. | Verificação de navegação por teclado e contraste nas telas principais. | `PLANNED` |
| `REQ-NFR-013` | Recuperação de Falhas | Interrupções inesperadas durante análise ou escrita não devem deixar estado inconsistente. | Reinicialização após falha simulada mantém integridade dos dados anteriores. | `PLANNED` |
