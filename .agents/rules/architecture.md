# Regra: Arquitetura

1. Não assumir ou implementar decisões arquiteturais ainda não aprovadas.
2. Toda decisão arquitetural relevante deve ser registrada como ADR em `vault/03-Architecture/ADR/` com estado explícito (`PROPOSED`, `ACCEPTED`, `REJECTED`, `SUPERSEDED`).
3. Não registrar propostas como decisões aprovadas (`ACCEPTED`).
4. A stack tecnológica permanece pendente até aprovação formal por ADR.
5. Respeitar os limites do produto:
   - Motor local e determinístico na V2.x.
   - Linguagens suportadas: Python, C# / .NET, Java e SQL.
   - Sem inteligência artificial no produto até a V3.0.
6. Não importar código automaticamente de implementações anteriores do POLARIS.
