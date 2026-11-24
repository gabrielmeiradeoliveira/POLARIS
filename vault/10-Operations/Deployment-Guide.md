# Guia de Implantação — POLARIS 2.0

## 1. Pré-requisitos
- Docker & Docker Compose
- Python 3.12+, .NET 8 SDK, JDK 21 (para execução local do Scanner)

## 2. Subindo o Ambiente Completo
```bash
docker compose up -d
```
Serviços expostos localmente:
- **PostgreSQL 17:** `127.0.0.1:5433`
- **POLARIS Server (API v1):** `http://127.0.0.1:8000`
- **POLARIS Web (UI):** `http://127.0.0.1:5173`

## 3. Variáveis de Ambiente
Consulte `.env.example` para configurar `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL` e `POLARIS_LOG_LEVEL`.
