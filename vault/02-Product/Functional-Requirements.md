---
id: DOC-008
title: Requisitos Funcionais
status: active
version: 2
created: 2026-11-14
updated: 2026-11-14
owner: product
tags:
  - polaris
  - product
  - functional-requirements
---

# Requisitos Funcionais — POLARIS 2.0

Todas as funcionalidades listadas abaixo encontram-se no estado `PLANNED`. Nenhum código de aplicação foi implementado no `GOAL-001`.

---

## REQ-FUNC-001 — Gerenciamento de Projetos
- **Identificador:** `REQ-FUNC-001`
- **Descrição:** Permitir criar, listar, configurar e remover projetos analisados pelo POLARIS.
- **Comportamento Esperado:** Cada projeto possui chave única (`projectKey`), nome, visibilidade e associação a Quality Profile e Quality Gate.
- **Referência Oficial:** `SQ-01` (SonarQube Server — Project Management)
- **Dependências Funcionais:** `REQ-FUNC-018`, `REQ-FUNC-019`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-001`):** Criar projeto via CLI/API/UI, impedir chaves duplicadas e isolar dados entre projetos.
- **Estratégia de Validação:** Testes de integração e E2E criando, consultando e removendo projetos reais.
- **Limitações:** Sem suporte a portfólios corporativos na V2.0 inicial.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-002 — Scanner
- **Identificador:** `REQ-FUNC-002`
- **Descrição:** CLI local responsável por varrer o código-fonte, coletar metadados, executar analisadores estáticos e enviar resultados ao servidor/armazenamento local.
- **Comportamento Esperado:** Execução determinística sobre diretórios locais sem executar o código-fonte analisado.
- **Referência Oficial:** `SQ-02` (SonarQube Scanner)
- **Dependências Funcionais:** `REQ-FUNC-001`, `REQ-FUNC-003`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-002`):** Executar scan em projeto válido e produzir relatório determinístico sem executar código analisado.
- **Estratégia de Validação:** Testes E2E e de segurança com amostras reais das 4 linguagens.
- **Limitações:** Análise restrita a Python, C# / .NET, Java e SQL.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-003 — Configuração de Análises
- **Identificador:** `REQ-FUNC-003`
- **Descrição:** Permitir configurar parâmetros de análise via arquivo de configuração do projeto (ex.: inclusões, exclusões, codificação, caminhos de cobertura).
- **Comportamento Esperado:** Ler configurações locais e aplicar filtros determinísticos de arquivos e diretórios.
- **Referência Oficial:** `SQ-03` (Analysis Scope & Parameters)
- **Dependências Funcionais:** `REQ-FUNC-002`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-003`):** Arquivos excluídos não são analisados; configurações inválidas retornam erro claro.
- **Estratégia de Validação:** Testes unitários e de integração com diferentes padrões de exclusão/inclusão.
- **Limitações:** A definir formato final do arquivo de configuração na fase de arquitetura (`GOAL-002`).
- **Estado Atual:** `PLANNED`

## REQ-FUNC-004 — Catálogo de Regras
- **Identificador:** `REQ-FUNC-004`
- **Descrição:** Manter catálogo versionado e determinístico de regras estáticas para Python, C# / .NET, Java e SQL.
- **Comportamento Esperado:** Cada regra possui ID único, linguagem, tipo (Bug, Vulnerability, Code Smell, Security Hotspot), severidade e tempo estimado de remediação.
- **Referência Oficial:** `SQ-04` (Rules Catalog)
- **Dependências Funcionais:** Nenhuma
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-004`):** Catálogo consultável por linguagem, tipo e severidade, com regras determinísticas.
- **Estratégia de Validação:** Testes de contrato e validação de regras contra casos positivos/negativos reais.
- **Limitações:** Sem regras baseadas em IA na V2.x.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-005 — Gerenciamento de Issues
- **Identificador:** `REQ-FUNC-005`
- **Descrição:** Registrar, classificar, filtrar e gerenciar o ciclo de vida das issues detectadas.
- **Comportamento Esperado:** Permitir visualizar arquivo/linha, regra violada, severidade e alterar estado (ex.: Open, Confirmed, False Positive, Won't Fix, Resolved).
- **Referência Oficial:** `SQ-05` (Issue Management)
- **Dependências Funcionais:** `REQ-FUNC-002`, `REQ-FUNC-004`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-005`):** Issues persistidas com rastreabilidade de linha/arquivo e transições de estado auditáveis.
- **Estratégia de Validação:** Testes de integração de persistência e E2E de triagem de issues.
- **Limitações:** Sem atribuição automática por IA.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-006 — Métricas de Qualidade
- **Identificador:** `REQ-FUNC-006`
- **Descrição:** Calcular e armazenar métricas quantitativas de qualidade por arquivo e projeto.
- **Comportamento Esperado:** Computar linhas de código (LOC), contagem de issues por tipo/severidade e ratings (Reliability, Security, Maintainability).
- **Referência Oficial:** `SQ-06` (Metrics)
- **Dependências Funcionais:** `REQ-FUNC-002`, `REQ-FUNC-005`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-006`):** Métricas calculadas de forma determinística e consistentes entre execuções idênticas.
- **Estratégia de Validação:** Testes unitários de cálculo e validação E2E em projetos de referência.
- **Limitações:** Conjunto inicial focado nas métricas essenciais para Quality Gates.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-007 — Complexidade
- **Identificador:** `REQ-FUNC-007`
- **Descrição:** Medir complexidade ciclomática e cognitiva de funções, métodos e classes.
- **Comportamento Esperado:** Calcular complexidade por unidade de código nas linguagens suportadas e agregar por arquivo/projeto.
- **Referência Oficial:** `SQ-07` (Complexity Metrics)
- **Dependências Funcionais:** `REQ-FUNC-006`
- **Prioridade Proposta:** Média (P2)
- **Critérios de Aceitação (`CA-FUNC-007`):** Cálculo determinístico validado contra amostras conhecidas em Python, C#, Java e SQL.
- **Estratégia de Validação:** Testes unitários com casos de referência por linguagem.
- **Limitações:** Precisão dependente do parser de cada linguagem.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-008 — Duplicação de Código
- **Identificador:** `REQ-FUNC-008`
- **Descrição:** Detectar blocos de código duplicados entre arquivos e dentro do mesmo arquivo.
- **Comportamento Esperado:** Calcular percentual de linhas duplicadas e listar blocos duplicados.
- **Referência Oficial:** `SQ-08` (Duplications)
- **Dependências Funcionais:** `REQ-FUNC-006`
- **Prioridade Proposta:** Média (P2)
- **Critérios de Aceitação (`CA-FUNC-008`):** Identificar duplicações exatas/estruturais dentro dos limiares configurados.
- **Estratégia de Validação:** Testes unitários e de integração com arquivos contendo duplicações conhecidas.
- **Limitações:** Detecção determinística baseada em tokens/AST, sem busca semântica por IA.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-009 — Cobertura de Testes
- **Identificador:** `REQ-FUNC-009`
- **Descrição:** Importar relatórios externos de cobertura de testes e calcular percentual de cobertura.
- **Comportamento Esperado:** Ler formatos padrão de cobertura (ex.: LCOV, Cobertura XML, JaCoCo XML) sem executar os testes do usuário.
- **Referência Oficial:** `SQ-09` (Test Coverage)
- **Dependências Funcionais:** `REQ-FUNC-003`, `REQ-FUNC-006`
- **Prioridade Proposta:** Média (P2)
- **Critérios de Aceitação (`CA-FUNC-009`):** Importar relatório válido e refletir cobertura por arquivo e projeto.
- **Estratégia de Validação:** Testes de integração com relatórios reais gerados por ferramentas padrão.
- **Limitações:** O POLARIS não executa a suíte de testes do projeto analisado.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-010 — Dívida Técnica
- **Identificador:** `REQ-FUNC-010`
- **Descrição:** Estimar o esforço de remediação (dívida técnica) acumulado a partir das issues abertas.
- **Comportamento Esperado:** Somar o esforço estimado por regra e calcular o Maintainability Rating (A–E).
- **Referência Oficial:** `SQ-10` (Technical Debt)
- **Dependências Funcionais:** `REQ-FUNC-004`, `REQ-FUNC-005`, `REQ-FUNC-006`
- **Prioridade Proposta:** Média (P2)
- **Critérios de Aceitação (`CA-FUNC-010`):** Dívida técnica expressa em tempo estimado e rating consistente com as regras.
- **Estratégia de Validação:** Testes unitários de agregação e validação E2E.
- **Limitações:** Baseado exclusivamente em pesos fixos das regras.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-011 — Quality Gates
- **Identificador:** `REQ-FUNC-011`
- **Descrição:** Avaliar automaticamente se um projeto atende aos critérios mínimos de qualidade (Pass/Fail).
- **Comportamento Esperado:** Comparar métricas de Código Novo e Código Geral contra limiares configurados e retornar status `PASSED` ou `FAILED`.
- **Referência Oficial:** `SQ-11` (Quality Gates)
- **Dependências Funcionais:** `REQ-FUNC-006`, `REQ-FUNC-014`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-011`):** Quality Gate padrão ("Polaris way") funcional e customizável; falha retorna código de saída não zero no CI/CD.
- **Estratégia de Validação:** Testes de integração e E2E simulando cenários de aprovação e reprovação.
- **Limitações:** Nenhuma limitação crítica prevista.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-012 — Quality Profiles
- **Identificador:** `REQ-FUNC-012`
- **Descrição:** Gerenciar conjuntos de regras ativos por linguagem para aplicação nas análises.
- **Comportamento Esperado:** Fornecer perfil padrão por linguagem e permitir criar, estender e ativar/desativar regras.
- **Referência Oficial:** `SQ-12` (Quality Profiles)
- **Dependências Funcionais:** `REQ-FUNC-004`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-012`):** Alterações no perfil refletem exatamente nas regras executadas pelo scanner.
- **Estratégia de Validação:** Testes de integração entre configuração do perfil e resultado do scanner.
- **Limitações:** Nenhuma limitação crítica prevista.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-013 — Histórico de Análises
- **Identificador:** `REQ-FUNC-013`
- **Descrição:** Armazenar snapshots históricos de análises para acompanhamento de evolução temporal.
- **Comportamento Esperado:** Registrar data, versão/commit, métricas e status do Quality Gate de cada análise.
- **Referência Oficial:** `SQ-13` (Activity & History)
- **Dependências Funcionais:** `REQ-FUNC-001`, `REQ-FUNC-006`
- **Prioridade Proposta:** Média (P2)
- **Critérios de Aceitação (`CA-FUNC-013`):** Consultar série histórica de métricas e comparar execuções anteriores.
- **Estratégia de Validação:** Testes de integração com múltiplas execuções sequenciais.
- **Limitações:** Retenção local sujeita a política de limpeza futura.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-014 — Análise de Código Novo
- **Identificador:** `REQ-FUNC-014`
- **Descrição:** Isolar métricas e issues introduzidas apenas no código novo ou modificado (metodologia Clean as You Code).
- **Comportamento Esperado:** Comparar contra baseline (versão anterior, data ou branch alvo) para destacar regressões recentes.
- **Referência Oficial:** `SQ-14` (New Code Definition)
- **Dependências Funcionais:** `REQ-FUNC-013`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-014`):** Issues legadas não falham condições de Código Novo no Quality Gate.
- **Estratégia de Validação:** Testes E2E com repositório Git contendo código legado e alterações novas.
- **Limitações:** Requer histórico Git ou baseline explícito.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-015 — Branches
- **Identificador:** `REQ-FUNC-015`
- **Descrição:** Suportar análise e rastreamento separado por branch de repositório Git.
- **Comportamento Esperado:** Manter métricas, issues e Quality Gate independentes por branch.
- **Referência Oficial:** `SQ-15` (Branch Analysis)
- **Dependências Funcionais:** `REQ-FUNC-001`, `REQ-FUNC-014`
- **Prioridade Proposta:** Média (P2)
- **Critérios de Aceitação (`CA-FUNC-015`):** Análises em branch de feature não sobrescrevem métricas da branch principal.
- **Estratégia de Validação:** Testes E2E analisando múltiplas branches de um mesmo projeto.
- **Limitações:** Focado em Git.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-016 — Pull Requests
- **Identificador:** `REQ-FUNC-016`
- **Descrição:** Analisar o delta de alterações de um Pull Request em relação à branch de destino.
- **Comportamento Esperado:** Avaliar apenas código alterado no PR e produzir relatório de status do Quality Gate.
- **Referência Oficial:** `SQ-16` (Pull Request Analysis)
- **Dependências Funcionais:** `REQ-FUNC-014`, `REQ-FUNC-015`
- **Prioridade Proposta:** Média (P2)
- **Critérios de Aceitação (`CA-FUNC-016`):** Reportar apenas issues introduzidas no PR e retornar status Pass/Fail.
- **Estratégia de Validação:** Testes E2E simulando diff entre branches.
- **Limitações:** Decoração direta em provedores externos (GitHub/GitLab) depende de integrações futuras.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-017 — Dashboard
- **Identificador:** `REQ-FUNC-017`
- **Descrição:** Interface web local para visualização de projetos, métricas, issues, Quality Gates e histórico.
- **Comportamento Esperado:** Exibir visão consolidada de Código Novo e Código Geral, navegação até a linha do arquivo com issue.
- **Referência Oficial:** `SQ-17` (SonarQube UI / Dashboard)
- **Dependências Funcionais:** `REQ-FUNC-020`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-017`):** Usuário consegue navegar do dashboard geral até o detalhe de uma issue real.
- **Estratégia de Validação:** Testes E2E de interface contra servidor e banco reais.
- **Limitações:** Interface local; sem recursos de IA.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-018 — Administração
- **Identificador:** `REQ-FUNC-018`
- **Descrição:** Configurações globais da instância local do POLARIS (retenção, padrões de Quality Gate/Profile, logs).
- **Comportamento Esperado:** Permitir ajustar configurações administrativas com persistência local.
- **Referência Oficial:** `SQ-18` (Administration)
- **Dependências Funcionais:** `REQ-FUNC-019`
- **Prioridade Proposta:** Média (P2)
- **Critérios de Aceitação (`CA-FUNC-018`):** Alterações administrativas persistem após reinicialização e afetam apenas usuários autorizados.
- **Estratégia de Validação:** Testes de integração e E2E.
- **Limitações:** Escopo restrito a instância única local.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-019 — Usuários e Permissões
- **Identificador:** `REQ-FUNC-019`
- **Descrição:** Autenticação local, gestão de tokens de análise e controle de acesso baseado em papéis (RBAC).
- **Comportamento Esperado:** Proteger operações administrativas e geração de tokens para o scanner.
- **Referência Oficial:** `SQ-19` (Users & Permissions)
- **Dependências Funcionais:** Nenhuma
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-019`):** Operações protegidas rejeitam requisições sem autenticação/permissão válida.
- **Estratégia de Validação:** Testes de integração de segurança e controle de acesso.
- **Limitações:** Autenticação local inicialmente (sem SSO/LDAP obrigatório na V2.0).
- **Estado Atual:** `PLANNED`

## REQ-FUNC-020 — API
- **Identificador:** `REQ-FUNC-020`
- **Descrição:** API HTTP local documentada para consulta de projetos, métricas, issues, Quality Gates e ingestão de análises.
- **Comportamento Esperado:** Endpoints determinísticos, versionados e protegidos por autenticação.
- **Referência Oficial:** `SQ-20` (Web API)
- **Dependências Funcionais:** `REQ-FUNC-019`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-020`):** Todos os endpoints principais respondem conforme contrato e validam entradas.
- **Estratégia de Validação:** Testes de contrato e integração contra servidor real.
- **Limitações:** API local.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-021 — Integrações CI/CD
- **Identificador:** `REQ-FUNC-021`
- **Descrição:** Permitir execução automatizada do scanner em pipelines CI/CD com verificação de Quality Gate.
- **Comportamento Esperado:** Retornar códigos de saída padronizados (0 para sucesso, diferente de 0 para falha de Quality Gate ou erro) e saída estruturada.
- **Referência Oficial:** `SQ-21` (CI/CD Integration)
- **Dependências Funcionais:** `REQ-FUNC-002`, `REQ-FUNC-011`
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-021`):** Pipeline local/CI falha quando Quality Gate falha e passa quando aprovado.
- **Estratégia de Validação:** Testes E2E em pipeline automatizado.
- **Limitações:** Execução via CLI.
- **Estado Atual:** `PLANNED`

## REQ-FUNC-022 — Instalação e Operação
- **Identificador:** `REQ-FUNC-022`
- **Descrição:** Processo simples e reproduzível para instalar, inicializar, atualizar e encerrar o POLARIS localmente.
- **Comportamento Esperado:** Comandos claros de inicialização, verificação de saúde (healthcheck) e persistência local de dados.
- **Referência Oficial:** `SQ-22` (Installation & Operations)
- **Dependências Funcionais:** Nenhuma
- **Prioridade Proposta:** Alta (P1)
- **Critérios de Aceitação (`CA-FUNC-022`):** Instalação limpa em ambiente suportado inicia e responde ao healthcheck sem erros.
- **Estratégia de Validação:** Testes de instalação em ambiente limpo.
- **Limitações:** Suporte restrito aos sistemas operacionais definidos após escolha da stack.
- **Estado Atual:** `PLANNED`
