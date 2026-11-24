---
id: DOC-011
title: Princípios Arquiteturais
status: active
version: 1
created: 2026-11-14
updated: 2026-11-14
owner: architecture
tags:
  - polaris
  - architecture
  - principles
---

# Princípios Arquiteturais

1. **Independência Arquitetural:** Nova implementação limpa, sem importação automática do POLARIS anterior ([ADR-001](ADR/ADR-001-Independent-Implementation.md)).
2. **Determinismo Local:** Execução local e determinística, sem IA na V2.x ([ADR-004](ADR/ADR-004-Deterministic-Engine-No-AI-V2.md)).
3. **Isolamento de Código Analisado:** Código submetido é tratado como não confiável e nunca executado automaticamente.
4. **Decisões Rastreáveis:** Toda decisão arquitetural relevante deve ser registrada em ADR.
5. **Simplicidade:** Evitar abstrações prematuras e dependências desnecessárias.
