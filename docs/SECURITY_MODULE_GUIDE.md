# POLARIS Security Module — Guia Operacional v1.7

## 1. Visão Geral
O Módulo de Segurança do POLARIS v1.7 fornece governança e inteligência unificada contra vulnerabilidades em código-fonte, configurações de contêiner (Dockerfiles), manifesto de dependências (Supply Chain), Software Bill of Materials (SBOM), Infrastructure as Code (IaC) e imagens de contêineres analisadas via Docker Scout.

---

## 2. Dependências e Pré-requisitos
- **Runtime:** Python 3.12+ (sem dependências de rede obrigatórias para varreduras determinísticas locais).
- **Docker Scout (Opcional):**
  - Docker Desktop ou Docker Engine com plugin `docker scout` (v1.21+).
  - Sessão autenticada (`docker login`) para geração de relatórios remotos de vulnerabilidade via Docker Hub.
  - Para ambientes sem internet / air-gapped: O POLARIS ingere relatórios SARIF 2.1.0 pré-gerados offline (`docker-scout.sarif`).

---

## 3. Comandos Principais e Fluxo de Uso

### A. Análise Local Integrada
```powershell
polaris review --provider fake --format terminal
```
Executa a suíte de scanners determinísticos (Container, Secrets, IaC, Supply Chain e Docker Scout) sobre as alterações staged/unstaged do repositório.

### B. Salvando e Comparando com Baseline de Segurança
```powershell
# Criação do Baseline Inicial:
polaris review --provider fake --save-baseline security_baseline.json

# Comparação subsequente com saída SARIF:
polaris review --provider fake --baseline security_baseline.json --format sarif
```

### C. Bloqueio em CI/CD estrito (Quality Gate)
Crie um arquivo `polaris.yaml` na raiz do projeto:
```yaml
policy:
  fail_on_severity:
    - CRITICAL
    - HIGH
  fail_on_new: true
  fail_on_incomplete: true
```
Execução no pipeline de CI/CD:
```powershell
polaris review --provider fake --baseline security_baseline.json --fail-on-new
```
**Códigos de Saída:**
- `0`: Sucesso / Quality Gate Aprovado.
- `1`: Violação de Política de Segurança (rejeição de vulnerabilidade nova ou de severidade bloqueante).
- `2`: Erro Operacional / Arquivo de baseline ou configuração corrompido.

---

## 4. Ingestão de Relatórios Docker Scout
Para incorporar varreduras de imagens de contêiner no relatório consolidado:
```powershell
# 1. Gerar o relatório SARIF pela ferramenta oficial:
docker scout cves --format sarif --output docker-scout.sarif local://minha-imagem:tag

# 2. Executar a revisão no POLARIS:
polaris review --provider fake --format json
```
O POLARIS detectará automaticamente o arquivo `docker-scout.sarif`, mapeará as CVEs para o domínio `IMAGE_VULNERABILITY`, correlacionará os componentes e aplicará as regras de Quality Gate e Baseline.

---

## 5. Resolução de Problemas (Troubleshooting)

| Sintoma | Causa Provável | Solução Recomendada |
|---|---|---|
| `docker scout: Log in with your Docker ID` | Scout requer autenticação prévia para consultar base de CVEs | Execute `docker login` ou forneça o arquivo SARIF pré-gerado. |
| Quality Gate retorna exit code 1 | Presença de vulnerabilidades bloqueantes (`CRITICAL`/`HIGH`) | Inspecione os findings no relatório SARIF/JSON e aplique as correções sugeridas em `remediation_hint`. |
| Relatório informa status `incomplete` | Orçamento de tokens esgotado ou scanner abortado | Aumente o budget com `--max-tokens` ou corrija erros de manifesto. O POLARIS nunca marca vulnerabilidades como resolvidas em análises incompletas. |
