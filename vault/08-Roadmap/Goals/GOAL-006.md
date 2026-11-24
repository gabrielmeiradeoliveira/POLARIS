---
id: GOAL-006
title: Implementação Completa dos Analisadores Especializados Multi-Linguagem
status: COMPLETED
priority: HIGH
depends_on:
  - GOAL-004
  - GOAL-005
version_target: 0.2.0
created: 2026-11-18
updated: 2026-11-18
owner: project
tags:
  - goal
  - analyzers
  - python
  - dotnet
  - java
  - sql
  - performance
  - testing
---

# GOAL-006 — Implementação Completa dos Analisadores Especializados Multi-Linguagem

## 1. Objetivo
Implementar, integrar e validar os quatro motores oficiais de análise estática determinística do **POLARIS 2.0** (**Python**, **C# / .NET**, **Java** e **SQL**), executando em processos isolados acionados pelo **POLARIS Scanner (CLI)** (`ADR-008`, `ADR-009`), emitindo exclusivamente o **Contrato de Análise Versionado v1** (`ADR-010`) e persistindo issues e métricas no **POLARIS Server** (`PostgreSQL 17`, `ADR-011`), com paridade funcional à **SonarQube Developer Edition 2026.5 LTA**.

---

## 2. Arquitetura de Execução e Isolamento (ADR-009 & ADR-010)

### 2.1. Protocolo de Comunicação Scanner ↔ Worker
- **Invocação:** O Scanner CLI descobre os arquivos do repositório alvo, agrupa por extensão e dispara um subprocesso por linguagem detectada.
- **Entrada (Manifesto JSON via `stdin` ou arquivo temporário):**
  - `project_root`: Caminho absoluto da raiz analisada.
  - `files`: Lista de caminhos relativos filtrados para aquela linguagem.
  - `active_rules`: Lista de IDs de regras habilitadas e parâmetros (ex.: limiar de complexidade ciclomática).
  - `timeout_seconds`: Limite máximo de execução do subprocesso.
- **Saída (`stdout`):** Payload JSON estritamente validado contra `AnalysisReportV1` (`issues` + `file_metrics`). Logs de diagnóstico e stack traces devem ir exclusivamente para `stderr`.
- **Códigos de Saída (Exit Codes):**
  - `0`: Análise concluída com sucesso (com ou sem issues encontradas).
  - `1`: Erro fatal de inicialização/ambiente (ex.: JDK ou SDK .NET ausente).
  - `2`: Falha parcial de parsing em um ou mais arquivos (o worker deve emitir o relatório dos arquivos válidos e registrar o erro em `stderr` sem abortar todo o lote).

---

## 3. Especificações Técnicas por Linguagem

### 3.1. Python (`vault/07-Languages/Python.md`)
- **Stack:** Python 3.12+ (`ast` nativo + `LibCST` + `Astroid`).
- **Responsabilidades por Camada:**
  - `LibCST`: Contagem exata de `ncloc` (ignorando linhas em branco e comentários), docstrings e regras baseadas em tokens/sintaxe concreta.
  - `ast` nativo: Cálculo de complexidade ciclomática, contagem de funções/classes e regras estruturais rápidas.
  - `Astroid`: Resolução semântica de escopo, inferência de tipos e análise inter-modular.
- **Catálogo Inicial de Regras (Mínimo 5 regras):**
  - `python:S1172` (*Code Smell* / `MINOR`): Parâmetro de função não utilizado.
  - `python:S1481` (*Code Smell* / `MINOR`): Variável local atribuída e nunca lida.
  - `python:S3776` (*Code Smell* / `CRITICAL`): Complexidade cognitiva/ciclomática acima do limiar (padrão: 15).
  - `python:S2068` (*Vulnerability* / `BLOCKER`): Credenciais ou segredos hardcoded detectados em literais.
  - `python:S5754` (*Bug* / `MAJOR`): Bloco `except:` genérico (bare except) ou captura silenciosa sem tratamento.

### 3.2. C# / .NET (`vault/07-Languages/DotNet.md`)
- **Stack:** .NET 8 Console Worker utilizando `Microsoft.CodeAnalysis.CSharp` (**Roslyn**).
- **Responsabilidades:**
  - Construção de `CSharpSyntaxTree` e `CSharpCompilation` / `SemanticModel` em memória (sem necessidade de build completo da solution quando não houver `.sln`, mas suportando referências básicas do runtime).
  - Consolidação e integração do motor de *Taint Analysis* (já prototipado no `cp03-csharp`) ao schema oficial `IssueV1`.
- **Catálogo Inicial de Regras (Mínimo 5 regras):**
  - `csharp:S1118` (*Code Smell* / `MAJOR`): Classes utilitárias (apenas membros `static`) sem construtor privado/protegido.
  - `csharp:S1481` (*Code Smell* / `MINOR`): Variável local não utilizada.
  - `csharp:S3776` (*Code Smell* / `CRITICAL`): Complexidade ciclomática excessiva em métodos.
  - `csharp:S2068` (*Vulnerability* / `BLOCKER`): Senhas ou chaves de conexão hardcoded.
  - `csharp:S3649` (*Vulnerability* / `BLOCKER`): Fluxo de *Taint* de entrada não sanitizada chegando a comandos SQL (`SqlCommand` / string interpolation).

### 3.3. Java (`vault/07-Languages/Java.md`)
- **Stack:** JDK 21 + Maven (empacotado como *fat-jar* executável) utilizando **JavaParser** + **JavaSymbolSolver**.
- **Responsabilidades:**
  - Parsing de arquivos `.java` (suporte até sintaxe Java 21) e resolução de tipos/símbolos via `CombinedTypeSolver` (`ReflectionTypeSolver` + `JavaParserTypeSolver` apontando para os diretórios `src/` do projeto).
- **Catálogo Inicial de Regras (Mínimo 5 regras):**
  - `java:S1118` (*Code Smell* / `MAJOR`): Classe utilitária sem construtor privado.
  - `java:S1481` (*Code Smell* / `MINOR`): Variável local não utilizada.
  - `java:S106` (*Code Smell* / `MAJOR`): Uso direto de `System.out` ou `System.err` em vez de logger estruturado.
  - `java:S2095` (*Bug* / `BLOCKER`): Recurso `Closeable` / `AutoCloseable` aberto sem `try-with-resources` ou `close()` garantido.
  - `java:S2068` (*Vulnerability* / `BLOCKER`): Credenciais hardcoded em literais `String`.

### 3.4. SQL (`vault/07-Languages/SQL.md`)
- **Stack:** Python 3.12+ utilizando **SQLGlot**.
- **Responsabilidades:**
  - Parsing multi-dialeto (prioridade: `postgres`, `tsql`, `ansi`) gerando AST padronizada para scripts `.sql` (DDL e DML).
- **Catálogo Inicial de Regras (Mínimo 5 regras):**
  - `sql:S1001` (*Code Smell* / `MAJOR`): Uso de `SELECT *` em consultas DML.
  - `sql:S1002` (*Bug* / `BLOCKER`): Instrução `UPDATE` ou `DELETE` sem cláusula `WHERE`.
  - `sql:S1003` (*Code Smell* / `CRITICAL`): `JOIN` explícito ou implícito sem condição `ON` / `USING` (produto cartesiano acidental).
  - `sql:S1004` (*Code Smell* / `MINOR`): Criação de tabela (`CREATE TABLE`) sem definição de `PRIMARY KEY`.
  - `sql:S1005` (*Vulnerability* / `CRITICAL`): Uso de SQL dinâmico (`EXECUTE` / `EXEC`) concatenado com literais.

---

## 4. Engenharia, Melhores Práticas e Pontos de Melhoria (Herdados do GOAL-004)

1. **Correção do Transporte de Payloads Grandes (Windows / Uvicorn):**
   - No fechamento do `GOAL-004`, o `test_03` evidenciou `ConnectionResetError` no transporte HTTP local sob payloads `> 10 MB`.
   - **Ação no GOAL-006:** Implementar compressão `Content-Encoding: gzip` no cliente HTTP do Scanner (`POST /api/v1/analyses`) com suporte transparente via middleware no FastAPI Server, além de configurar limites explícitos de corpo e streaming para análises de repositórios grandes.
2. **Isolamento de Dependências e Build Reprodutível:**
   - Adicionar targets claros no `Makefile` / scripts de build (`build-analyzers`) para compilar o binário .NET (Roslyn) e o JAR Maven (JavaParser) de forma determinística, validando a presença dos runtimes no comando `polaris doctor` / `polaris --check-env`.
3. **Determinismo Absoluto:**
   - Ordenar determinísticamente as listas `issues` (por `file_path`, `line`, `rule_id`) e `metrics` (por `file_path`) antes da serialização JSON, garantindo hashes idênticos entre execuções repetidas no mesmo commit.
4. **Resiliência a Arquivos Malformados:**
   - Erros de sintaxe em um arquivo específico do repositório analisado nunca devem derrubar o worker; o erro deve ser logado em `stderr` com o caminho do arquivo e a análise dos demais arquivos deve prosseguir normalmente.

---

## 5. Requisitos de Performance e Escalabilidade

1. **Processamento em Lote (Batch-per-Language):**
   - O Scanner **nunca** deve iniciar um subprocesso por arquivo (o overhead de inicialização da JVM e do CLR inviabilizaria a execução). Deve haver **no máximo 1 invocação de subprocesso por linguagem** por execução do Scanner.
2. **Execução Paralela entre Linguagens:**
   - Quando um repositório contiver múltiplas linguagens (ex.: backend C#/Java + scripts Python + migrations SQL), o Scanner deve executar os workers em paralelo (`asyncio.gather` / `ThreadPoolExecutor`), respeitando o limite de núcleos da CPU.
3. **Metas de Latência (Benchmarks Locais):**
   - **Startup + Análise de 100 arquivos médios (~15.000 NCLOC):**
     - Worker Python: `< 2.5s`
     - Worker SQL (SQLGlot): `< 1.5s`
     - Worker C# (Roslyn): `< 4.0s`
     - Worker Java (JavaParser): `< 4.5s`
4. **Gestão de Memória:**
   - Limitar explicitamente o heap da JVM (`-Xmx512m` ou configurável via env) no subprocesso Java para evitar consumo descontrolado em ambientes locais Docker/CI.

---

## 6. Estratégia e Modelos de Teste (`vault/06-Quality/Testing-Strategy.md`)

### 6.1. Pirâmide de Testes Obrigatória
1. **Testes Unitários de Regras (por Linguagem):**
   - Para cada uma das 20+ regras implementadas (mínimo 5 por linguagem), criar pares explícitos:
     - `compliant` (código limpo que **não** deve disparar issue — prevenção de falsos positivos).
     - `non_compliant` (código defeituoso que **deve** disparar a issue na linha exata — prevenção de falsos negativos).
2. **Golden Tests de Contrato (`Contract Compliance Tests`):**
   - Fixtures de código-fonte de referência para Python, C#, Java e SQL com saída JSON esperada congelada (`golden_report.json`).
   - Validação estrita via `AnalysisReportV1.model_validate_json(...)` garantindo campos obrigatórios, tipos, severidades e determinismo de ordenação.
3. **Testes de Resiliência e Falha Controlada:**
   - Arquivo com erro de sintaxe severo misturado a arquivos válidos (deve retornar `exit_code = 2` ou `0` com warning e preservar issues dos arquivos válidos).
   - Timeout forçado de subprocesso (garantir que o Scanner encerra o processo filho sem deixar processos órfãos).
4. **Teste de Integração End-to-End Polyglot (`E2E-GOAL-006`):**
   - Executar o `polaris-scanner` contra um repositório fixture contendo simultaneamente `.py`, `.cs`, `.java` e `.sql`.
   - Validar o envio gzipado para `POST /api/v1/analyses`, persistência no PostgreSQL 17 (porta `5433`) e consulta consolidada via `GET /api/v1/projects/{key}/issues`.

---

## 7. Critérios de Aceitação (Definition of Done — `vault/06-Quality/Definition-of-Done.md`)
- [ ] Os 4 workers (`python`, `csharp`, `java`, `sql`) estão implementados e documentados em `vault/07-Languages/`.
- [ ] Mínimo de 5 regras funcionais (cobrindo *Bug*, *Vulnerability* e *Code Smell*) e métricas base (`ncloc`, `complexity`, `functions`) operacionais em cada uma das 4 linguagens.
- [ ] Transporte HTTP com suporte a compressão `gzip` implementado e validado com payload `> 10 MB` (resolvendo a limitação observada no `test_03` do `GOAL-004`).
- [ ] 100% dos testes unitários, *golden tests* de contrato e teste E2E polyglot passando em ambiente limpo.
- [ ] Benchmarks de tempo de execução registrados e dentro das metas estabelecidas na Seção 5.
- [ ] Evidência formal registrada em `vault/09-Validation/Reports/VAL-GOAL-006-FINAL.md` e indexada em `vault/09-Validation/Index.md`.
- [ ] `Current-State.md` atualizado para a versão `0.2.0`.
