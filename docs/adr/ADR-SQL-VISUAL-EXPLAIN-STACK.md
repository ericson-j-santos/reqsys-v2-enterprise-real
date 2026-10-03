# ADR — SQL Visual Explain Stack

## Status

Proposto

## Contexto

O ReqSys deve evoluir para apoiar análise de SQL com foco em aprendizado, explicabilidade, documentação viva, rastreabilidade e governança.

A consulta analisada no actuallyEXPLAIN demonstrou valor para transformar SQL em intenção lógica navegável.

## Decisão

Adotar duas trilhas complementares:

1. **Trilha didática:** actuallyEXPLAIN + IA + DBeaver/pgAdmin.
2. **Trilha enterprise:** DBeaver/DataGrip + PostgreSQL EXPLAIN ANALYZE + SQLGlot + Mermaid/ERD versionado.

## Consequências positivas

- Melhora a leitura de consultas por negócio, engenharia e dados.
- Cria base para documentação viva de SQL.
- Permite evolução futura para linhagem, impacto e explicabilidade automatizada.
- Mantém Git como fonte da verdade.

## Riscos

| Risco | Mitigação |
|---|---|
| Parser heurístico incompleto | Evoluir para SQLGlot no próximo incremento |
| EXPLAIN ANALYZE em produção | Executar apenas em ambiente controlado ou com limites |
| Documentação divergente do código | Automatizar geração em CI |

## Próxima decisão

Evoluir o analisador para SQLGlot e integrar geração automática de relatório Mermaid/Markdown no pipeline.
