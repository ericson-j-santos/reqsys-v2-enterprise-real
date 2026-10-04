# Live Traceability Change Impact — Requisitos

## Objetivo

Conectar o `functional_traceability_graph` vivo do ReqSys ao Impact Engine sem criar nova fonte de verdade e sem substituir o dataset histórico usado exclusivamente para benchmark.

## Requisitos

1. O Impact Engine deve aceitar uma mudança operacional sem exigir `ground_truth`.
2. Os candidatos operacionais devem ser derivados somente de `nodes[]` e `edges[]` do grafo vivo.
3. O adaptador deve validar `graph_type=functional_traceability_graph`.
4. Arestas com `evidence_status=rejected` não podem alimentar candidatos operacionais por padrão.
5. Evidência rejeitada deve continuar disponível no grafo de origem para diagnóstico, sem ser promovida pelo Impact Engine.
6. IDs retornados pelo LLM devem continuar limitados ao conjunto previamente recuperado; ID inexistente deve ser descartado.
7. A saída do LLM não pode criar evidência canônica nem alterar o grafo.
8. O benchmark histórico e `HistoricalChange.ground_truth` devem permanecer disponíveis apenas para avaliação reproduzível.
9. O fluxo deve permanecer read-only, sem migração de banco, Neo4j, deploy ou mutação de produção.
10. O E2E deve exercitar API FastAPI real → grafo vivo → Impact Engine, incluindo controle negativo de runtime rejeitado e alucinação de ID.

## Critérios de aceite

1. Um grafo positivo produzido por `GET /v1/rastreabilidade/requisitos/{id}/grafo` gera candidatos nas estratégias graph, semantic e hybrid.
2. Todos os candidatos retornados pertencem aos IDs do grafo vivo.
3. Com `runtime_sha != head_sha`, os nós de CI/deploy/runtime ligados apenas por evidência rejeitada ficam fora do conjunto operacional padrão.
4. Um LLM que devolva um ID inexistente tem esse ID descartado e não o transforma em evidência.
5. O caminho histórico continua executável sem alteração de contrato de benchmark.
6. Pre-PR Readiness deve ficar verde no HEAD exato antes da abertura da PR.
