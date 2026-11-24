---
id: DOC-041
title: Jornadas do Usuário
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: product
tags:
  - polaris
  - product
  - user-journeys
---

# Jornadas do Usuário — POLARIS 2.0

Todas as jornadas abaixo estão no estado `PLANNED`. Nenhuma interface foi implementada neste GOAL.

## UJ-001 — Instalar o POLARIS
- **Pré-condições:** Ambiente compatível com os pré-requisitos da plataforma.
- **Etapas:** Baixar/instalar o pacote do POLARIS -> Verificar instalação via CLI.
- **Resultado Esperado:** Binário/serviço instalado e pronto para inicialização.
- **Critério de Aceitação (`CA-UJ-001`):** Comando de versão/ajuda responde corretamente em instalação limpa.

## UJ-002 — Inicializar a Plataforma
- **Pré-condições:** POLARIS instalado (`UJ-001`).
- **Etapas:** Executar comando de inicialização -> Aguardar subida do serviço local e armazenamento -> Acessar UI/API local.
- **Resultado Esperado:** Plataforma operacional e respondendo ao healthcheck.
- **Critério de Aceitação (`CA-UJ-002`):** Healthcheck retorna sucesso e usuário administrador inicial está disponível.

## UJ-003 — Criar um Projeto
- **Pré-condições:** Plataforma inicializada e usuário autenticado.
- **Etapas:** Acessar criação de projeto -> Informar nome e `projectKey` -> Confirmar criação.
- **Resultado Esperado:** Projeto criado e pronto para receber análises.
- **Critério de Aceitação (`CA-UJ-003`):** Projeto aparece na listagem e possui token/configuração de análise disponível.

## UJ-004 — Configurar uma Análise
- **Pré-condições:** Projeto criado (`UJ-003`) e código-fonte local disponível.
- **Etapas:** Criar arquivo de configuração no repositório -> Definir `projectKey`, diretórios de origem e exclusões.
- **Resultado Esperado:** Configuração válida reconhecida pelo scanner.
- **Critério de Aceitação (`CA-UJ-004`):** Scanner lê a configuração e aplica exatamente o escopo definido.

## UJ-005 — Executar o Scanner
- **Pré-condições:** Análise configurada (`UJ-004`) e plataforma operacional.
- **Etapas:** Executar comando do scanner apontando para o projeto -> Aguardar análise estática -> Enviar resultados.
- **Resultado Esperado:** Análise concluída e publicada no projeto local.
- **Critério de Aceitação (`CA-UJ-005`):** Scanner finaliza sem erro e dados ficam disponíveis na API/Dashboard.

## UJ-006 — Consultar Resultados
- **Pré-condições:** Pelo menos uma análise concluída (`UJ-005`).
- **Etapas:** Abrir o projeto no Dashboard -> Visualizar status do Quality Gate, resumo de Código Novo e Código Geral.
- **Resultado Esperado:** Visão consolidada e fiel aos dados da última análise.
- **Critério de Aceitação (`CA-UJ-006`):** Status do Quality Gate e contadores principais exibidos corretamente.

## UJ-007 — Navegar pelas Métricas
- **Pré-condições:** Análise concluída (`UJ-005`).
- **Etapas:** Acessar aba de métricas -> Filtrar por diretório/arquivo -> Inspecionar LOC, complexidade, duplicação e cobertura.
- **Resultado Esperado:** Detalhamento hierárquico das métricas por arquivo.
- **Critério de Aceitação (`CA-UJ-007`):** Valores agregados do projeto correspondem à soma/agregação dos arquivos.

## UJ-008 — Gerenciar Issues
- **Pré-condições:** Análise com issues detectadas.
- **Etapas:** Filtrar issues por severidade/tipo/arquivo -> Abrir trecho de código afetado -> Alterar estado (ex.: Confirmed, False Positive).
- **Resultado Esperado:** Estado da issue atualizado e auditável.
- **Critério de Aceitação (`CA-UJ-008`):** Alteração persiste e recalcula métricas/Quality Gate quando aplicável.

## UJ-009 — Configurar Quality Profiles
- **Pré-condições:** Usuário com permissão administrativa.
- **Etapas:** Selecionar linguagem (Python, C#, Java ou SQL) -> Criar ou estender perfil -> Ativar/desativar regras -> Associar ao projeto.
- **Resultado Esperado:** Próxima análise do projeto utiliza o perfil configurado.
- **Critério de Aceitação (`CA-UJ-009`):** Regras desativadas não geram issues na análise subsequente.

## UJ-010 — Configurar Quality Gates
- **Pré-condições:** Usuário com permissão administrativa.
- **Etapas:** Criar ou editar Quality Gate -> Definir condições e limiares -> Associar ao projeto.
- **Resultado Esperado:** Avaliações futuras aplicam as novas condições.
- **Critério de Aceitação (`CA-UJ-010`):** Projeto falha no Quality Gate quando uma condição configurada é violada.

## UJ-011 — Consultar o Histórico
- **Pré-condições:** Múltiplas análises executadas no projeto.
- **Etapas:** Acessar aba de histórico/atividade -> Selecionar intervalo ou métrica -> Comparar evolução.
- **Resultado Esperado:** Linha do tempo com snapshots anteriores.
- **Critério de Aceitação (`CA-UJ-011`):** Histórico preserva resultados de análises passadas sem sobrescrevê-los.

## UJ-012 — Integrar a Análise ao CI/CD
- **Pré-condições:** Pipeline CI/CD configurado com acesso ao scanner e token de análise.
- **Etapas:** Configurar etapa de scan no pipeline -> Habilitar verificação do Quality Gate -> Executar pipeline.
- **Resultado Esperado:** Pipeline aprova ou bloqueia automaticamente conforme o Quality Gate.
- **Critério de Aceitação (`CA-UJ-012`):** Código de saída do scanner reflete o resultado real do Quality Gate.
