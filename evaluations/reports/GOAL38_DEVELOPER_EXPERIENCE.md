# POLARIS — GOAL 38: DEVELOPER EXPERIENCE & PRODUCT INTERFACES

**Data:** 2026-11-08
**Status:** **ACCEPTED WITH LIMITATIONS**
**Implementação:** `src/polaris/reporting/sarif.py`
**Testes:** `tests/test_github_gate_and_sarif.py`

---

## 1. Capacidades
- Formato de exportação padrão SARIF v2.1.0 para integração direta com GitHub Security Code Scanning tab.
- Preservação estrita dos comandos existentes no CLI `polaris`.
- Relatórios explicáveis conectando achados, mecanismos determinísticos e custos de token.
