# POLARIS — GOAL 36: GITHUB-NATIVE REVIEW ENGINE

**Data:** 2026-11-08
**Status:** **ACCEPTED WITH LIMITATIONS**
**Implementação:** `src/polaris/integrations/github/review_native.py`
**Testes:** `tests/test_github_gate_and_sarif.py`

---

## 1. Capacidades
- Verificação segura de assinatura HMAC-SHA256 para webhooks do GitHub (`verify_webhook_signature`).
- Mapeamento determinístico de comentários inline para linhas e hunks de diff do PR (`PullRequestReviewComment`).
- Emissão de payload de review estruturado com suporte a comentários idempotentes e execução dry-run 100% offline.
