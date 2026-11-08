# POLARIS — GOAL 29.1: Registro de Riscos Técnicos e Lacunas

> **Documento:** `GOAL29_RISK_REGISTER.md`

---

## 1. Riscos Técnicos Mapeados

| ID | Área | Descrição do Risco | Impacto | Mitigação no GOAL 29 |
| :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | Orçamento | Concorrência de threads/processos gerando reservas órfãs sob interrupção abrupta. | Médio | Fase 29.2: Reconciliação conservadora e persistência transacional com limpeza de reservas expiradas. |
| **RSK-02** | Contexto | Arm ON concatenando arquivos completos em vez de trechos ponderados por AST/relevância. | Alto | Fase 29.3: Integração direta do `ContextRanker` e `BehavioralDelta` ao `HybridReviewOrchestrator`. |
| **RSK-03** | Segurança | Regras AST cobrindo apenas relaxamento de disjunção (`None`), deixando brechas em remoção de validações e auth flags. | Alto | Fase 29.4: Implementação de 5 novas regras determinísticas no `SecurityGuardrailEngine` (SEC-AUTH-002 a 006). |
| **RSK-04** | Contratos | Análise de contratos restrita a dicionários literais, ignorando TypedDict, tuplas, dataclasses e assinaturas. | Médio | Fase 29.5: Expansão do `CrossFileContractEngine` para estruturas ricas e anotações de tipo. |
| **RSK-05** | Arbitragem | Findings concorrentes na mesma linha com descrições divergentes gerando agrupamentos ambíguos. | Baixo | Fase 29.6: Refinamento de clusterização semântica por símbolo AST e cálculo de distância causal. |
| **RSK-06** | Observabilidade | Métricas híbridas isoladas não serializadas no relatório JSON padrão do POLARIS. | Médio | Fase 29.8: Formatação canônica de telemetria híbrida em `AnalysisReport`. |
| **RSK-07** | Performance | Grafos de importação cíclicos densos consumindo tempo excessivo em repositórios grandes. | Médio | Fase 29.10: Limites de expansão BFS e testes de stress sintéticos. |
