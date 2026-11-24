---
id: VAL-003-AUDIT
title: Auditoria da Prova de Conceito (poc/goal-003)
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: qa
tags:
  - polaris
  - audit
  - goal-003
---

# Auditoria da Prova de Conceito (`poc/goal-003/`)

## 1. Motivo da Reabertura (`GOAL-003-R1`)

O relatório inicial do `GOAL-003` validou uma integração vertical mínima em Python/SQLite, mas **não comprovou** a adequação da stack tecnológica para a paridade com o SonarQube. Critérios obrigatórios (avaliação comparativa de Backend, Scanner, Roslyn, Eclipse JDT/JavaParser, LibCST/Astroid, SQLGlot/ScriptDom, PostgreSQL, React/Vue, 20+ regras experimentais, precisão/recall/F1 e testes completos de segurança) não foram executados.

## 2. Inventário Técnico de `poc/goal-003/`

| Arquivo | Papel | Dependências |
| :--- | :--- | :--- |
| `analyzers.py` | 4 analisadores experimentais | Biblioteca padrão Python (`ast`, `re`, `hashlib`) |
| `scanner.py` | Descoberta de arquivos e envio HTTP | Biblioteca padrão Python (`pathlib`, `urllib.request`) |
| `server.py` | Servidor HTTP + SQLite + HTML mínimo | Biblioteca padrão Python (`http.server`, `sqlite3`) |
| `test_poc.py` | 2 testes (`PARSE_ERROR` e E2E) | `unittest` |
| `benchmark.py` | Benchmark com 200 arquivos sintéticos | `time`, `tracemalloc` |
| `samples/` | 4 arquivos de amostra (`app.py`, `Program.cs`, `Main.java`, `query.sql`) | N/A |

## 3. Capacidades Reais dos Analisadores na PoC

| Analisador | Técnica Real Utilizada | Regra Implementada | Limitações (Não Possui) |
| :--- | :--- | :--- | :--- |
| **Python** | **AST** (`ast.parse`) | `PY-S001` (`eval`/`exec`) | Sem resolução de símbolos, tipos, fluxo de controle/dados ou taint analysis. |
| **C# / .NET** | **Busca textual / Regex** | `CS-M001` (`Console.WriteLine`) | Sem parsing, sem AST, sem Roslyn, sem resolução semântica. |
| **Java** | **Busca textual / Regex** | `JV-M001` (`System.out.println`) | Sem parsing, sem AST, sem Eclipse JDT/JavaParser, sem resolução semântica. |
| **SQL** | **Regex** (`\bSELECT\s+\*`) | `SQL-M001` (`SELECT *`) | Sem parsing SQL real, sem diferenciação de dialetos. |

## 4. Auditoria do Benchmark Existente

- **Geração:** 200 arquivos sintéticos (50 por linguagem) com 1 a 4 linhas cada.
- **Regras:** 1 regra simples por linguagem.
- **Medição:** `time.perf_counter()` e `tracemalloc.get_traced_memory()` (mede apenas memória rastreada pelo alocador Python, não o RSS total do processo).
- **Conclusão:** Válido apenas como baseline de I/O e parsing trivial em Python; não representa análise semântica real.
