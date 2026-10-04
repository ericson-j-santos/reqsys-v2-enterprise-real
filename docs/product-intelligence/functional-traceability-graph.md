# Functional Traceability Graph

## Objetivo

Criar grafo funcional de rastreabilidade para conectar requisitos, PRs, testes, decisões e riscos dentro da camada `ReqSys Product Intelligence Layer`.

## Capacidades implementadas

- Builder Python sem dependências externas.
- Geração de grafo funcional em JSON.
- Relatório navegável em Markdown.
- Relatório visual em HTML.
- Cálculo de cobertura de rastreabilidade.
- Recomendação objetiva de melhoria.
- Workflow CI dedicado.
- Artifact de grafo funcional.

## Nós iniciais

| Tipo | Descrição |
|---|---|
| requirement | Requisito funcional ou não funcional |
| pull_request | PR vinculado à implementação |
| test | Teste vinculado à validação |
| decision | Decisão funcional/arquitetural |
| risk | Risco funcional vinculado |

## Relações iniciais

| Relação | Significado |
|---|---|
| parent | Requisito pai |
| implemented_by | Implementado por PR |
| validated_by | Validado por teste |
| decided_by | Amparado por decisão |
| exposed_to | Exposto a risco |

## Métricas

| Métrica | Descrição |
|---|---|
| node_count | Quantidade de nós no grafo |
| edge_count | Quantidade de relações |
| traceability_coverage_score | Cobertura de grupos de rastreabilidade preenchidos |

## Limites

- Não altera runtime produtivo.
- Não adiciona dependências externas.
- Não executa agentes automaticamente.
- Não integra bases corporativas reais.
- Não altera gates operacionais existentes.

## Próximo incremento recomendado

ReqSys Product Intelligence Dashboard.
