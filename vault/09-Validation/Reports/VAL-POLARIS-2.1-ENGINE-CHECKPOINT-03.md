---
id: VAL-POLARIS-2.1-ENGINE-CHECKPOINT-03
title: Checkpoint 03 do Motor Avançado — POLARIS 2.1
type: validation-report
status: IN_PROGRESS
created_at: 2026-11-15
updated_at: 2026-11-15
tags: [polaris-2.1, csharp, scanner, flow-steps, checkpoint-03]
---

# Checkpoint 03 do Motor Avançado — POLARIS 2.1

## 1. Integração Scanner → Motor C# → FlowSteps → API

- `polaris-scanner analyze` executado contra projeto C# multi-arquivo (`UserController.cs` -> `UserService.cs` -> `UserRepository.cs`).
- `src/polaris_server/issues_service.py`: Adicionados `cwe`, `flow_steps` e endpoint `GET /api/v1/issues/{issue_id}/flow`.
- `tests/integration/test_checkpoint03_scanner_flow.py`: `1/1 OK` (`0.533s`) — comprovou emissão de `CS-TAINT-001` (`CWE-89`), 4 `flowSteps` nos 3 arquivos, persistência e consulta via `get_issue_flow`.
