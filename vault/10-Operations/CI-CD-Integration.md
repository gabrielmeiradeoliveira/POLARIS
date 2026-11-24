# Integração CI/CD — POLARIS 2.0

## GitHub Actions (Exemplo)
```yaml
- name: Run POLARIS Scanner
  env:
    POLARIS_TOKEN: ${{ secrets.POLARIS_TOKEN }}
  run: |
    python -m polaris_scanner.cli analyze \
      --target . \
      --project my-repo \
      --server http://127.0.0.1:8000 \
      --target-branch main \
      --pr-key PR-${{ github.event.number }} \
      --fail-on-quality-gate
```
- `exit_code = 0`: Quality Gate `PASSED`.
- `exit_code = 3`: Quality Gate `FAILED` (bloqueia o merge).
