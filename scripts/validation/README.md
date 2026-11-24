# Validação Documental — `validate-docs.ps1`

Este script valida a integridade documental do repositório POLARIS 2.0 sem depender de caminhos absolutos de máquina.

## O que é verificado

- Existência de arquivos `.md` vazios.
- Presença de frontmatter YAML válido (`id`, `title`, `status`) em todos os documentos de `vault/`.
- Unicidade de identificadores (`id`) no frontmatter (ignorando templates com `XXX`).
- Integridade de links internos Markdown para arquivos `.md`.

## Como executar

A partir da raiz do repositório:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validation/validate-docs.ps1
```
