# POLARIS — GOAL 32: CONTAINER SECURITY INTELLIGENCE

**Data:** 2026-11-08
**Status:** **ACCEPTED WITH LIMITATIONS**
**Implementação:** `src/polaris/container/scanner.py`
**Testes:** `tests/test_container_security.py` (2 passed)

---

## 1. Capacidades
- Inspeção offline de instruções de Dockerfile.
- Identificação de ausência de usuário não-root (`ROOT_USER_EXECUTION`).
- Detecção de base images com tag `:latest` ou não fixadas.
- Detecção de segredos hardcoded em instruções `ENV` e `RUN`.
- Detecção de scripts remotos canalizados diretamente para o shell (`curl ... | bash`).
