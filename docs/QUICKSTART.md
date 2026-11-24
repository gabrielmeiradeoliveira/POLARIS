# POLARIS Quickstart (5 Minutes)

## 1. Local Dev (`--changed-only` in ~250ms)
```bash
PYTHONPATH=src python -m polaris_scanner.cli analyze --target . --changed-only
```

## 2. Low-Spec Docker Stack (<= 1.2 GB RAM)
```bash
docker compose -f docker-compose.low-spec.yml up -d
```

## 3. CI/CD (SARIF 2.1.0 + CycloneDX 1.5 SBOM)
```bash
PYTHONPATH=src python -m polaris_scanner.cli analyze --target . --project my-app --format sarif --output polaris.sarif --sbom-out sbom.cdx.json
```
