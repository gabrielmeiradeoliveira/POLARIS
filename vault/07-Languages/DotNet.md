---
id: DOC-028
title: Linguagem Suportada — C# / .NET
status: active
version: 2
created: 2026-11-14
updated: 2026-11-14
owner: product
tags:
  - polaris
  - languages
  - dotnet
  - csharp
---

# C# / .NET

C# / .NET é uma das quatro linguagens oficialmente suportadas pelo POLARIS 2.0 ([ADR-003](../03-Architecture/ADR/ADR-003-Supported-Languages.md)).

## Ecossistema e Formatos de Projeto (Referência)
- **Arquivos-fonte:** `.cs`
- **Descritores de projeto comuns:** `.sln`, `.csproj`, `Directory.Build.props`
- **Relatórios de cobertura comuns:** OpenCover, Cobertura XML, Visual Studio Coverage

## Propostas Pendentes de Decisão
- Versões de C# e .NET suportadas (ex.: .NET 6/8/9, .NET Framework legado).
- Estratégia de análise estática sem compilação/execução de código não confiável.
- Conjunto inicial de regras de paridade com SonarQube.
