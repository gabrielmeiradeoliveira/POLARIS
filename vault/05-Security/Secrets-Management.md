---
id: DOC-020
title: Gestão de Segredos
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: security
tags:
  - polaris
  - security
  - secrets
---

# Gestão de Segredos

- É estritamente proibido versionar senhas, tokens, chaves de API, certificados privados ou arquivos `.env` no repositório.
- O arquivo `.gitignore` bloqueia padrões comuns de segredos (`.env`, `*.pem`, `*.key`, `secrets/`).
- Logs da aplicação e relatórios de validação nunca devem conter segredos ou credenciais.
