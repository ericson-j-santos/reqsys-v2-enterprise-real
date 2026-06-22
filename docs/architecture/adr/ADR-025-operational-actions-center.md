# ADR-025 — ReqSys Operational Actions Center

## Status

Proposto.

## Contexto

A operação do ReqSys passou a depender de múltiplos workflows GitHub Actions, dispatchers, CI Router, deploys e validações de governança. A validação manual por link ou run id aumenta o tempo de resposta e gera lacunas de rastreabilidade.

## Decisão

Implementar o `Operational Actions Center` como capability transversal para capturar e classificar execuções do GitHub Actions.

## Escopo P0

- Serviço de normalização de workflow runs.
- Classificação operacional: healthy, running, unhealthy e unknown.
- Score de saúde dos workflows.
- Endpoint autenticado de status.
- Endpoint para snapshot manual de runs.
- Endpoint admin para consultar runs recentes via GitHub API.
- Endpoint admin para receber eventos de webhook GitHub.
- Testes unitários do classificador.

## Fora do P0

- Persistência histórica em banco.
- Dashboards frontend completos.
- Self-healing automático.
- Reexecução automática de jobs.
- Webhook sem autenticação interna dedicada.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Exposição de token GitHub | usar somente variáveis de ambiente e nunca retornar token na API |
| Falha de GitHub API | retornar erro 502 com mensagem operacional |
| Ruído por runs em andamento | classificar `running` separadamente |
| Decisão errada de merge | score não substitui revisão humana em falhas críticas |

## Evolução recomendada

- Persistir histórico em tabela própria.
- Criar painel Vue no Runtime Center.
- Integrar retry governado.
- Criar ranking Pareto de falhas.
- Adicionar métricas DORA e MTTR.
