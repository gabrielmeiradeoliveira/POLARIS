---
id: VAL-003-R1
title: Relatório de Auditoria e Reavaliação do GOAL-003
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: qa
tags:
  - polaris
  - validation
  - goal-003-r1
---

# VAL-003-R1 — Auditoria e Reavaliação do GOAL-003

- **Identificador:** `GOAL-003` (`GOAL-003-R1`)
- **Data:** `2026-11-14`
- **Estado Final:** `BLOCKED`

## 1. Inventário Real do Ambiente

Comando executado:
```powershell
Get-Command python, java, javac, mvn, gradle, dotnet, node, npm, go, docker, psql -ErrorAction SilentlyContinue | Select-Object Name, Source | Format-Table -AutoSize
```

- **Instalados no PATH:** `python.exe` (3.12.10), `java.exe` (OpenJDK 25.0.4.1), `javac.exe`, `dotnet.exe` (11.0.100), `node.exe` (v24.18.0), `npm.ps1`, `docker.exe`.
- **Não instalados / Ausentes do PATH:** `mvn` (Maven), `gradle` (Gradle), `go` (Go), `psql` (PostgreSQL).
- **Restrição Adicional:** Sandbox sem acesso à rede impede download de pacotes NuGet, PyPI, Maven Central e npm.

## 2. Verificação da Referência SonarQube

- Confirmado na documentação oficial (`docs.sonarsource.com`): **SonarQube Server 2026.5 LTA** é a versão LTA atual (sucessora da 2026.1 LTA).

## 3. Reavaliação dos Critérios de Aceitação (Resumo)

- **PASS:** Auditoria da PoC (`AUDIT-POC-GOAL-003.md`), inventário real do ambiente, preservação de `VAL-GOAL-003.md`, verificação da versão SonarQube (`2026.5 LTA`), integração vertical baseline (`poc/goal-003/`).
- **BLOCKED:** Avaliação comparativa de Backend (Spring Boot/ASP.NET), Scanner (Go/Java), Analisadores semânticos (Roslyn, Eclipse JDT/JavaParser, LibCST/Astroid, SQLGlot/ScriptDom), PostgreSQL, Frontend (React/Vue), 20+ regras experimentais com corpus de precisão/recall/F1 e suíte completa de segurança.

## 4. Instruções Objetivas para Desbloqueio

1. Instalar ou adicionar ao PATH: **Maven** (`mvn`), **PostgreSQL** (`psql` ou container Docker) e **Go** (se mantido como candidato de Scanner).
2. Autorizar acesso à rede (ou fornecer cache offline/artifactory local) para instalação de pacotes de PoC: NuGet (`Microsoft.CodeAnalysis.CSharp`, `Microsoft.SqlServer.TransactSql.ScriptDom`), PyPI (`libcst`, `astroid`, `sqlglot`), Maven (`javaparser-symbol-solver-core`) e npm (`react`, `typescript`).
3. Reautorizar a execução dos experimentos após o desbloqueio.
