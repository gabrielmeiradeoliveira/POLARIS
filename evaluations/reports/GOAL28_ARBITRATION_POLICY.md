# POLARIS — GOAL 28: Política de Arbitragem e Resolução de Conflitos

> **Documento:** `GOAL28_ARBITRATION_POLICY.md`
> **Escopo:** Motor de Arbitragem e Consolidação (`polaris.intelligence.arbitration`)
> **Modo de Operação:** Determinístico, independente da ordem de entrada, auditável via Evidence Registry.

---

## 1. Topologia de Proveniência e Evidence Registry

O Evidence Registry (`EvidenceRecord`) calcula hashes estáveis via SHA-256 baseados nos atributos semânticos (`source`, `file`, `start_line`, `end_line`, `symbol`, `property_or_contract`, `confidence`, `description`).

Fontes registradas:
- `STATIC_SECURITY`: Achados determinísticos do Security Guardrail Engine.
- `STATIC_CONTRACT`: Achados interprocedurais do Cross-File Contract Engine.
- `OFF_DIFF_ONLY`: Achados primários baseados exclusivamente no diff local.
- `ON_BEHAVIORAL_DELTA`: Achados semânticos enriquecidos com callers e contratos.

---

## 2. As Seis Regras Obrigatórias de Arbitragem

### Regra A — Preservação Inviolável de Segurança (Caso 11)
- Um finding de segurança com evidência estática `CONFIRMED` não pode ser removido pela ausência de alerta no Arm ON.
- É promovido com status `CONFIRMED` e nota de divergência documentando que o contexto do Arm ON omitiu a violação.

### Regra B — Divergência Arm OFF / Arm ON
- Se o Arm OFF detectar um defeito e o Arm ON retornar vazio (sem confirmação estática), o finding é preservado com proveniência do OFF e status `DISPUTED`.
- A ausência de alerta no Arm ON **não constitui prova de falso positivo**, prevenindo a supressão por atenção diluída.

### Regra C — Refinamento Taxonômico sem Duplicação (Caso 5)
- Se Arm OFF e Arm ON identificarem o mesmo defeito local na mesma entidade, mas com categorias divergentes (ex.: OFF diagnosticou `TYPE_MISMATCH` e ON diagnosticou `NULL_HANDLING`), o motor adota a categoria mais bem fundamentada (`NULL_HANDLING`), preservando a proveniência de ambas as fontes e emitindo **exatamente um finding consolidado**.

### Regra D — Incerteza Estática Preservada (Caso 9)
- Achados de análise interprocedural de contratos que dependam de parâmetros não resolvidos estaticamente recebem nível `SUSPECTED` e **não são promovidos artificialmente a `CONFIRMED`**.

### Regra E — Concordância e Corroboração
- Quando múltiplas fontes concordam sobre a localização e o defeito, o status consolidado é definido como `CORROBORATED`, agrupando todas as evidências.

### Regra F — Tolerância a Falhas Operacionais
- Falhas de rede, timeouts ou limites de cota no Arm ON resultam em `ExecutionState.FAILED` ou `TIMEOUT`, marcando `partial_failure = True` na telemetria e **preservando integralmente** os achados válidos do Arm OFF e dos analisadores estáticos.
