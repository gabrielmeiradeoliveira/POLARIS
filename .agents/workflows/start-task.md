# Workflow: start-task

## Objetivo
Iniciar qualquer tarefa no projeto POLARIS garantindo leitura prévia da documentação oficial e alinhamento de escopo.

## Pré-requisitos
- Tarefa ou GOAL formalmente autorizado.

## Documentos Obrigatórios
1. `AGENTS.md`
2. `vault/00-Home.md`
3. `vault/01-Project/Current-State.md`
4. `vault/08-Roadmap/Roadmap.md`
5. `vault/08-Roadmap/Goals/Index.md`
6. Documento do GOAL correspondente
7. Regras relevantes de `.agents/rules/`

## Etapas
1. Ler os documentos obrigatórios na ordem definida.
2. Inspecionar o diretório e os arquivos relevantes ao escopo.
3. Identificar requisitos, restrições, ADRs vigentes e riscos.
4. Confirmar que a tarefa não viola o escopo do GOAL ativo.
5. Registrar o início ou plano da tarefa quando aplicável.

## Restrições
- Não iniciar implementação sem compreender os requisitos.
- Não assumir decisões arquiteturais pendentes.

## Critérios de Aceitação
- Contexto, escopo e restrições da tarefa claramente compreendidos.

## Evidências Exigidas
- Lista de documentos consultados e arquivos inspecionados.

## Condições de Bloqueio
- Conflito não resolvido entre documentos.
- Requisito ambíguo ou fora de escopo sem autorização.
