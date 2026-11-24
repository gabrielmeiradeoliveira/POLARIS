---
id: DOC-029
title: Linguagem Suportada — Java
status: active
version: 2
created: 2026-11-14
updated: 2026-11-14
owner: product
tags:
  - polaris
  - languages
  - java
---

# Java

Java é uma das quatro linguagens oficialmente suportadas pelo POLARIS 2.0 ([ADR-003](../03-Architecture/ADR/ADR-003-Supported-Languages.md)).

## Ecossistema e Formatos de Projeto (Referência)
- **Arquivos-fonte:** `.java`
- **Descritores de projeto comuns:** `pom.xml` (Maven), `build.gradle` / `build.gradle.kts` (Gradle)
- **Relatórios de cobertura comuns:** JaCoCo XML

## Propostas Pendentes de Decisão
- Versões do Java/JDK suportadas (ex.: Java 11, 17, 21).
- Estratégia de análise baseada em código-fonte vs bytecode (respeitando política de não execução).
- Conjunto inicial de regras de paridade com SonarQube.
