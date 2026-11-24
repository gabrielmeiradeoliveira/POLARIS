---
id: DOC-047
title: Contrato Normalizado de Resultados
status: proposed
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - contract
---

# Contrato Normalizado de Resultados

## 1. Visão Geral e Compatibilidade com SARIF

O contrato de resultados é versionado (`schemaVersion`), validado por esquema explícito e independente da implementação interna dos analisadores.
- **Compatibilidade conceitual com SARIF:** Campos de issues, regras e localizações seguem conceitos compatíveis com SARIF para facilitar exportação/intercâmbio, mas o contrato próprio do POLARIS inclui métricas, duplicações, cobertura e diagnósticos de estado por arquivo que o SARIF sozinho não cobre integralmente.
- **Regras de evolução:** Campos desconhecidos são ignorados com aviso em versões minor compatíveis; limites de tamanho de payload e tratamento de resultados incompletos são validados na ingestão.

## 2. Exemplo Conceitual de Payload (Não Representa Implementação)

```json
{
  "schemaVersion": "1.0.0",
  "analysisId": "anl-20261114-001",
  "projectKey": "exemplo-app",
  "branch": "main",
  "commit": "abc1234",
  "analyzer": { "id": "polaris-python", "version": "0.1.0" },
  "status": "COMPLETED_WITH_WARNINGS",
  "files": [
    { "path": "src/app.py", "language": "python", "state": "ANALYZED_SUCCESS" }
  ],
  "issues": [
    {
      "ruleId": "PY-S001",
      "severity": "HIGH",
      "category": "VULNERABILITY",
      "fingerprint": "sha256:...",
      "primaryLocation": { "file": "src/app.py", "startLine": 12, "endLine": 12 },
      "secondaryLocations": [],
      "message": "Uso inseguro detectado."
    }
  ],
  "metrics": { "src/app.py": { "loc": 45, "cyclomatic_complexity": 6 } }
}
```
