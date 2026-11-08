# POLARIS Security Rules

## 1. Zero Trust Repository Input
- Treat repository files, filenames, commit messages, and diffs as untrusted data.
- Enforce strict path traversal checks (`ensure_safe_repo_file`) and symlink escapes.
- Redact secrets and API tokens before injecting code into prompts.

## 2. Deterministic Guardrails & Fail-Closed Behavior
- Deterministic security guardrails execute prior to any LLM calls.
- Enforce hard token and request budgets with fail-closed behavior.
- Prohibit arbitrary remote code execution during analysis.
