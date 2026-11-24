---
id: VAL-GOAL-004-C
title: Relatório de Validação — GOAL-004-C (Scanner Definitivo e Contratos Compartilhados)
type: validation-report
status: COMPLETED
created_at: 2026-11-15
updated_at: 2026-11-15
tags: [validation, goal-004-c, scanner, contracts]
---

# Relatório de Validação — GOAL-004-C

## 1. Resumo Executivo

- **Estado do GOAL-004-C:** `COMPLETED` (29/29 critérios `PASS` em [GOAL-004-C.json](file:///C:/Users/gabri/OneDrive/%C3%81rea%20de%20Trabalho/POLARIS%202.0/vault/09-Validation/Acceptance/GOAL-004-C.json))
- **Estado do GOAL-004 Principal:** `IN_PROGRESS` (mantido conforme escopo autorizado)

## 2. Implementação Realizada

- `src/polaris_scanner/config.py`: `ScannerConfig` tipado com precedência `CLI > env > polaris.json > defaults` e validação estrita.
- `src/polaris_scanner/discovery.py`: Descoberta determinística para `.py`, `.cs`, `.java` e `.sql`, suporte a espaços e Unicode, exclusões padrão e customizadas, proteção contra symlinks e path traversal (`followlinks=False`, `is_symlink()`, `is_relative_to()`), e limites de arquivo/contagem/tamanho total.
- `src/polaris_scanner/registry.py`: Registro de analisadores confiáveis (`polaris-python-analyzer`, `polaris-csharp-analyzer`, `polaris-java-analyzer`, `polaris-sql-analyzer`).
- `src/polaris_scanner/executor.py`: Execução segura de subprocessos (`shell=False`), limites de `stdout`/`stderr`, timeout, e tratamento de exit codes não-zero e JSON inválido.
- `src/polaris_scanner/contracts.py`: Validação do contrato `1.0.0` (localização 1-based, caminhos POSIX relativos, estados e diagnósticos) e escrita atômica UTF-8 (`write_report_atomic`).
- `src/polaris_scanner/cli.py`: CLI completa com `--version`, `--help`, subcomando `discover`, flags e exit codes `0`, `1` e `2`.

## 3. Evidências de Testes Executados

| Suíte | Comando | Resultado |
| :--- | :--- | :--- |
| Unitários Scanner | `.\.venv\Scripts\python.exe -m unittest discover -s tests/unit/scanner -v` | `10/10 OK` |
| Unitários Contratos | `.\.venv\Scripts\python.exe -m unittest discover -s tests/unit/contracts -v` | `3/3 OK` |
| Contrato Cross-Runtime | `.\.venv\Scripts\python.exe -m unittest discover -s tests/contract -v` | `2/2 OK` |
| Integração CLI | `.\.venv\Scripts\python.exe -m unittest discover -s tests/integration/scanner -v` | `3/3 OK` |
| Fundação (Regressão) | `.\.venv\Scripts\python.exe tests/test_foundation.py` | `2/2 OK` |
