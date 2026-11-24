# Workflow: update-documentation

## Objetivo
Manter o `vault/` e os documentos da raiz sincronizados com o estado real do projeto.

## Pré-requisitos
- Alteração realizada ou decisão tomada.

## Documentos Obrigatórios
1. `.agents/rules/documentation.md`
2. `vault/00-Home.md`
3. `vault/01-Project/Current-State.md`

## Etapas
1. Identificar todos os documentos impactados pela alteração.
2. Atualizar conteúdo, frontmatter YAML (`updated`, `version`, `status`) e links internos.
3. Registrar decisões em `vault/11-History/Decision-Log.md` ou ADRs em `vault/03-Architecture/ADR/`.
4. Registrar mudanças em `vault/11-History/Development-Log.md`.
5. Validar integridade de links e metadados YAML.

## Restrições
- Não criar arquivos vazios.
- Não registrar propostas como decisões aprovadas.

## Critérios de Aceitação
- Documentação consistente, navegável e fiel ao estado real do repositório.

## Evidências Exigidas
- Lista de documentos atualizados e resultado da verificação de links/YAML.

## Condições de Bloqueio
- Inconsistência entre documentação e implementação real.
