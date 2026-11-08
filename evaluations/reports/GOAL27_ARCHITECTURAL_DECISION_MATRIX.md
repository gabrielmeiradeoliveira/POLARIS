# POLARIS — Matriz de Decisão Arquitetural e Estratégia de Análise (GOAL 27)

> **Documento Preparatório Exclusivamente Offline — Versão Revisada**
> **Base de Evidências Medidas:** 14 pares concluídos e auditados (12 positivos com defeitos reais + 2 controles negativos limpos)
> **Status da Campanha:** Congelada aguardando cota NVIDIA (`2026-11-09T00:00:00Z`) para os 6 controles negativos restantes (`e2e-ctx-15` a `e2e-ctx-20`).

---

## 1. Contexto e Motivação

O **GOAL 27** introduziu a infraestrutura de avaliação pareada e reproduzível para comparar o impacto do **Behavioral Delta** (contexto semântico expandido com callers, testes, contratos de módulo e propagação de estado) em relação à revisão tradicional restrita ao diff sintático.

A análise empírica dos 14 pares concluídos revelou fenômenos qualitativos e quantitativos críticos:
- O **Arm OFF (Diff puro)** demonstrou sensibilidade local imediata, detectando inclusive alterações sutis de segurança no diff (Caso 11), porém gerou **alucinação de categoria** no Caso 5 (`type_mismatch` em vez de `null_handling`), acarretando simultaneamente 1 FP e 1 FN no avaliador.
- O **Arm ON (Behavioral Delta)** eliminou **100% dos falsos positivos** nos 14 casos medidos e resolveu com precisão o Caso 5, mas introduziu um **risco crítico não mitigado de supressão por dispersão de atenção (Attention Dilution)** no Caso 11 (`permission-default-multiple-callers`), onde a presença dos chamadores externos diluiu a percepção de risco do LLM sobre uma vulnerabilidade de permissão no diff.
- A **Estratégia Híbrida** é tratada neste documento estritamente como **projeção e limite teórico**, distinguindo claramente uma simples união ideal de findings de uma arquitetura implementada com desduplicação e resolução de conflitos.

---

## 2. Matriz Comparativa: Evidências Medidas vs. Projeções Teóricas

| Dimensão de Avaliação | Arm OFF (Diff Puro)<br>*(Evidência Medida — 14 Casos)* | Arm ON (Behavioral Delta)<br>*(Evidência Medida — 14 Casos)* | Estratégia Híbrida<br>*(Projeção / Limite Teórico)* |
| :--- | :--- | :--- | :--- |
| **Precisão** | **90.9%** (10 TP / 11 findings) | **100.0%** (10 TP / 10 findings) | **~90.9% – 100.0%** *(Projeção condicionada à regra de desduplicação)* |
| **Recall** | **83.3%** (10 TP / 12 defeitos) | **83.3%** (10 TP / 12 defeitos) | **91.7%** *(Limite teórico da união: 11 TP / 12)* |
| **F1-Score** | **86.9%** | **90.9%** | **~91.3% – 95.6%** *(Projeção teórica)* |
| **Falsos Positivos (FP)** | **1 FP** (Caso 5: category mismatch) | **0 FP** (Zero falsos alarmes nos 14 casos) | **0 a 1 FP** *(Projeção: depende se descarta ou herda o FP do OFF)* |
| **Falsos Negativos (FN)** | **2 FN** (Casos 5 e 9) | **2 FN** (Casos 9 e 11) | **1 FN** *(Limite teórico da união: apenas Caso 9)* |
| **Detecção de Riscos Críticos** | **Detectou** vulnerabilidade no diff (Caso 11). | **Suprimiu** finding de permissão (**Risco Crítico Não Mitigado**). | **Requer lógica de arbitragem** para não herdar a supressão do ON. |
| **Tokens Consumidos (Total 14 Casos)** | **20.752 tokens** (13.137 prompt + 7.615 comp) | **23.532 tokens** (14.648 prompt + 8.884 comp) | **~30.000 a 44.000 tokens** *(Projeção: +28% a +100% sobre OFF)* |
| **Tokens / Caso (Média, Mediana, P90)** | Média: **1.482,3** \| Med: **1.484,0** \| P90: **1.851** | Média: **1.680,9** \| Med: **1.601,5** \| P90: **2.473** | *Projeção: ~2.100 a 3.100 tokens/caso dependendo da seletividade* |
| **Latência / Caso (Média, Mediana, P90)** | Média: **24,1s** \| Med: **22,1s** \| P90: **40,6s** | Média: **38,1s** \| Med: **28,0s** \| P90: **97,5s** | *Projeção: ~38s (se paralelo assíncrono) ou >60s (se sequencial)* |
| **Complexidade Operacional** | **Mínima** (1 chamada, infraestrutura simples) | **Baixa-Média** (extração de callers/AST + 1 chamada) | **Alta** (orquestração de múltiplos passos, deduplicação e árbitro) |

---

## 3. Análise Detalhada dos Casos e Riscos

### 3.1. Caso 5 (`null-plugin-result`): Correção Semântica por Contexto
- **Arm OFF:** O modelo detectou retorno nulo mas diagnosticou como `type_mismatch` (categoria não aceita pela especificação do defeito: exige `null_handling` ou `correctness`). Gerou simultaneamente **FP=1 e FN=1**.
- **Arm ON:** Com os contratos dos chamadores fornecidos pelo Behavioral Delta, o modelo compreendeu o impacto operacional e emitiu `null_handling` exato com severidade `HIGH` (**TP=1, FP=0, FN=0**).
- **Evidência confirmada:** O contexto semântico é altamente eficaz para corrigir a taxonomia de findings e evitar falsos alarmes conceituais.

### 3.2. Caso 9 (`indirect-serializer-contract`): Limite de Atenção de Múltiplos Saltos
- **Ambos os braços falharam (FN=1 em OFF e ON):** Nenhum finding foi gerado em nenhum dos braços (`candidate_findings: []`).
- **Causa técnica:** A quebra do contrato envolvia um encadeamento de 3 níveis no serializador. Nem o diff isolado nem o Behavioral Delta padrão em um único passo de inferência ativaram o raciocínio profundo necessário.
- **Evidência confirmada:** Defeitos arquiteturais indiretos exigem análise determinística de taint/fluxo de dados ou passos encadeados de verificação, não sendo resolvidos apenas pela injeção bruta de contexto.

### 3.3. Caso 11 (`permission-default-multiple-callers`): Risco Crítico de Supressão (Não Mitigado)
- **Arm OFF:** Identificou prontamente o desvio de segurança no valor padrão de permissão como `logic_error` (**TP=1, FP=0, FN=0**).
- **Arm ON:** Ao receber os chamadores, a atenção do modelo foi diluída pelo código adicional periférico e o finding de permissão **foi completamente suprimido (FN=1)**.
- **Alerta de Segurança:** O caso 11 constitui um **risco crítico ativo e não mitigado**. O Behavioral Delta pode mascarar falhas graves de autorização se o contexto atenuar a percepção de perigo de uma modificação local no diff.

---

## 4. Diferenciação Crucial na Estratégia Híbrida: Limite Teórico vs. Implementação Real

É imperativo distinguir **a união teórica de findings** de uma **estratégia híbrida operacional**:

1. **União Teórica (Oráculo / Upper Bound):**
   - Se tomássemos retrospectivamente o melhor resultado entre OFF e ON para cada caso, teríamos 11 TP e apenas 1 FN (Caso 9), atingindo Recall de 91.7%.
   - **Isso é uma abstração analítica, não um algoritmo.** Em tempo real de execução, o sistema não sabe a priori qual braço acertou.
2. **Implementação Real de Estratégia Híbrida (Desafios e Riscos Operacionais):**
   - **Deduplicação de Findings:** Se OFF reportar `type_mismatch` e ON reportar `null_handling` na mesma linha (como no Caso 5), um reconciliador ingênuo pode emitir **dois findings** para o mesmo bug, mantendo o falso positivo do OFF.
   - **Resolução de Conflitos e Supressão:** Se ON suprimir um finding que OFF emitiu (como no Caso 11), a estratégia deve decidir: aceita o finding do OFF (arrisca herdar falsos positivos) ou descarta pelo veredito do ON (arrisca herdar o falso negativo de segurança)?
   - **Custo Operacional e de Latência:** Executar ambos os braços dobra a quantidade de requisições HTTP, tornando a operação mais custosa e propensa a esgotar cotas de rate limit (ex.: 20 RPD na NVIDIA NIM).

---

## 5. Delimitação Estrita do Escopo dos Casos 15 a 20

Os casos restantes (`e2e-ctx-15` a `e2e-ctx-20`) são **exclusivamente controles negativos limpos** (`expected_defects = 0`):
- Refatorações de código seguras.
- Otimizações internas de algoritmos sem quebra de contrato.
- Migrações de bibliotecas sem alteração de comportamento externo.

> [!WARNING]
> **Limitação Amostral dos Controles Negativos:**
> A execução dos casos 15 a 20 **não contém novos defeitos de segurança**. Portanto, a conclusão destes casos **NÃO PODE comprovar** que a falha de supressão observada no Caso 11 foi um evento isolado ou que o risco está mitigado.
> O objetivo exclusivo dos casos 15 a 20 é medir a **taxa de falsos positivos (especificidade)** de ambos os braços sob código correto e o custo de tokens em PRs sem defeito.

---

## 6. Critérios Objetivos de Decisão Pós-GOAL 27

A decisão arquitetural para as próximas fases do POLARIS será pautada pelos seguintes critérios objetivos após a conclusão dos 20 casos:

| Critério de Decisão | Condição Observada | Implicação Arquitetural |
| :--- | :--- | :--- |
| **Taxa de Falso Positivo nos 8 Controles** | Arm ON = 0 FP e Arm OFF ≥ 2 FP | Comprova que o **Arm OFF é inviável como solução isolada** devido ao volume de ruído em PRs limpos. |
| **Risco de Supressão de Segurança** | Caso 11 permanece sem mitigação arquitetural | **Impede a adoção irrestrita do Arm ON como padrão cego**. Exige obrigatoriamente um guardrail ou camada de sensibilidade estática para regras de segurança. |
| **Estratégia Híbrida Condicional** | Necessidade de unir sensibilidade do diff com precisão do contexto | Justificada **somente se** for desenvolvido um módulo determinístico de arbitragem que resolva conflitos sem duplicar FPs nem silenciar FNs de segurança. |
| **Restrição Orçamentária e de Cota** | Limite free tier (20 RPD / 100k tokens) | Qualquer abordagem multi-chamada deve prever fallback para diff puro quando a cota estiver restrita. |

### Conclusão Preliminar
O Arm ON demonstra **superioridade categórica na eliminação de falsos positivos**, mas o Caso 11 impede que ele seja considerado uma solução completa sem salvaguardas adicionais. A evolução arquitetural do POLARIS exigirá um design consciente desse trade-off, priorizando a segurança contra supressão sem comprometer a precisão alcançada.
