---
id: VAL-POLARIS-2.1-ENGINE-CHECKPOINT-02
title: Checkpoint 02 do Motor Avançado — POLARIS 2.1
type: validation-report
status: IN_PROGRESS
created_at: 2026-11-15
updated_at: 2026-11-15
tags: [polaris-2.1, csharp, roslyn, taint, checkpoint-02]
---

# Checkpoint 02 do Motor Avançado — POLARIS 2.1

## 1. Integração e Execução Real do Motor C#

- `analyzers/csharp/Program.cs` integrado com `PolarisCSharpAnalyzer.SemanticTaintEngine.AnalyzeProject(projectFiles)`.
- `dotnet build analyzers/csharp/PolarisCSharpAnalyzer.csproj -c Release`: `Build succeeded. 0 Warning(s) 0 Error(s)` (`1.90s`).
- `tests/integration/test_csharp_taint_e2e.py`: `1/1 OK` (`0.737s`) executando `dotnet exec analyzers/csharp/bin/Release/net10.0/PolarisCSharpAnalyzer.dll`:
  - **Caso vulnerável (`UserController.cs` -> `UserService.cs` -> `UserRepository.cs`):** Emitiu `CS-TAINT-001` (`CWE-89`) com `flowSteps` contendo os 3 arquivos.
  - **Variante parametrizada (`SqlParameter`):** `0` ocorrências de `CS-TAINT-001`.
