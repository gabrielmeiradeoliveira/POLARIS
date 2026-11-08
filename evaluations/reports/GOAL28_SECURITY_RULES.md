# POLARIS — GOAL 28: Regras de Segurança e Guardrails Estáticos

> **Documento:** `GOAL28_SECURITY_RULES.md`  
> **Escopo:** Regras determinísticas implementadas no Security Guardrail Engine (`polaris.guardrails`)  
> **Modo de Operação:** 100% offline, baseado em AST Python, zero execução dinâmica.

---

## 1. Princípios e Invariantes Fundamentais

1. **Inviolabilidade de Segurança:** Um finding de segurança classificado com nível de certeza `CONFIRMED` **jamais pode ser descartado** por ausência de achados em modelos de linguagem (Arm OFF ou Arm ON).
2. **Rejeição a Heurísticas Textuais:** Nenhuma regra pode disparar simplesmente pela presença de identificadores ou nomes como `auth`, `admin`, `security` ou `role`. A decisão deve ser embasada em transformações estruturais da Árvore Sintática Abstrata (AST).
3. **Escada de Certeza Estrita:**
   - `CONFIRMED`: A violação semântica é formalmente demonstrável no subconjunto de linguagem suportado.
   - `SUSPECTED`: Há evidência estrutural, mas o impacto depende de tipos, chamadas externas ou estados dinâmicos não resolvidos.
   - `UNKNOWN`: Construções dinâmicas fora do escopo estático (ex.: reflexão, `eval`).

---

## 2. Catálogo de Regras Implementadas

### Regra `SEC-AUTH-001`: Relaxamento de Autorização (Allow-by-Default / Aceite de `None`)

- **Identificador:** `SEC-AUTH-001`
- **Categoria:** `LOGIC_ERROR`
- **Severidade:** `HIGH`
- **Padrão Semântico Detectado:**
  - Identifica funções responsáveis por verificar acesso onde uma condição restritiva anterior (ex.: `role == 'admin'`) é expandida através de uma disjunção (`or`) que aceita expressamente `None` para um parâmetro funcional (ex.: `role is None or role == 'admin'`).
  - Detecta a transição de **deny-by-default** (onde omitir o parâmetro resultava em acesso negado) para **allow-by-default** (onde omitir o parâmetro concede autorização).
- **Tratamento de Expressões Complexas:**
  - Se a nova expressão contiver chamadas de funções dinâmicas externas (ex.: `role is None or verify_remote(role)`), o guardrail registra nível `SUSPECTED` em vez de `CONFIRMED`, documentando a limitação estática.
- **Caso de Referência do Benchmark:** **Caso 11** (`e2e-ctx-11-permission-default-multiple-callers`).

---

## 3. Limitações Conhecidas do Analisador

- **Não avalia:** `getattr`, chamadas dinâmicas polimórficas, despacho de métodos por string ou monkey-patching em runtime.
- **Tamanho de Arquivo:** Arquivos com tamanho superior a 500 KB são ignorados de forma controlada sem gerar falsos alertas.
- **Sintaxe Inválida:** Arquivos com `SyntaxError` resultam em falha segura (zero findings emitidos, sem interrupção por exceções não tratadas).
