# ADR-020 — Query Intelligence Platform

## Status

Implementado como incremento inicial em branch de feature.

## Contexto

O ReqSys precisa evoluir a análise, explicação e governança de consultas SQL utilizadas em requisitos, BI, RAG, automações e integrações corporativas.

A referência visual observada no actuallyEXPLAIN demonstra valor em transformar SQL em intenção lógica, diagramas e navegação estrutural. Para o ReqSys, essa capacidade deve ser tratada como módulo enterprise, auditável e extensível.

## Decisão

Criar o módulo **Query Intelligence Platform** como capacidade transversal do ReqSys, responsável por:

- receber SQL informado por usuário, requisito, relatório ou integração;
- gerar análise estática inicial;
- identificar tabelas, aliases, joins, filtros, ordenações, agregações, CTEs e funções de janela;
- calcular score de risco;
- produzir grafo lógico navegável;
- gerar explicação textual da intenção lógica;
- registrar achados de governança;
- preparar integração futura com EXPLAIN real, OpenTelemetry, lineage e IA explicável.

## Escopo implementado

- Parser heurístico seguro, sem execução de SQL.
- Analisador de risco estático.
- Modelo de grafo lógico para UI.
- Interface navegável com editor SQL, indicadores, achados, explicação e diagrama simplificado.
- Testes unitários do núcleo de análise.

## Fora do escopo inicial

- Execução de SQL em banco real.
- EXPLAIN ANALYZE runtime.
- Persistência em banco.
- Integração com catálogos corporativos.
- Classificação LGPD baseada em dicionário corporativo real.

## Princípios obrigatórios

- Nenhum SQL deve ser executado nesse módulo inicial.
- SQL informado deve ser tratado como entrada não confiável.
- Produção não pode depender de parser externo sem fallback.
- Toda análise deve diferenciar evidência detectada de inferência.
- Score de risco deve ser conservador.
- Não registrar tokens, senhas, connection strings ou dados sensíveis em logs.

## Modelo de maturidade

| Capacidade | Estado inicial | Alvo |
|---|---:|---:|
| Parsing estático | Implementado | Multi-engine |
| Grafo lógico | Implementado | Lineage corporativo |
| Risk scoring | Implementado | Políticas configuráveis |
| IA explicável | Heurística | LLM governado |
| Runtime EXPLAIN | Não implementado | Integrado |
| Observabilidade | Preparado | OpenTelemetry |

## Consequências

### Positivas

- Cria base para SQL lineage vivo.
- Permite análise governada antes de publicar consultas.
- Melhora explicabilidade de BI, RAG e automações.
- Reduz risco de queries opacas, pesadas ou inseguras.

### Riscos

- Parser heurístico pode não cobrir todos os dialetos.
- Pode haver falsos positivos em risco.
- Sem catálogo corporativo, PII é inferida apenas por nomes de campos.

## Próximos incrementos

1. Persistir histórico de análises.
2. Integrar com OpenTelemetry.
3. Adicionar adaptador SQL Server/PostgreSQL para EXPLAIN seguro em sandbox.
4. Criar políticas configuráveis de governança SQL.
5. Integrar com requisitos, dashboards e RAG.
