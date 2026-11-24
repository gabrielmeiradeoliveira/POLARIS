# Runbook de Troubleshooting — POLARIS 2.0

## 1. Saúde dos Serviços
- Liveness: `GET /health/live`
- Readiness (PostgreSQL 17): `GET /health/ready`
- Métricas: `GET /metrics`

## 2. Erros Comuns
- **Porta 5433 já alocada:** Verifique containers ativos com `docker ps` e remova instâncias antigas antes de rodar `docker compose up -d`.
- **Logs estruturados:** Cada requisição HTTP retorna `X-Request-ID` para correlação nos logs JSON do servidor.
