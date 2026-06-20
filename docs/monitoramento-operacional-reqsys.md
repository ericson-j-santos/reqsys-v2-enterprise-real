# Monitoramento Operacional ReqSys

## Status

Proposto como incremento mínimo de observabilidade operacional associado à frente `REQSYS-OPER-004`.

## Objetivo

Criar uma base canônica para que o ReqSys acompanhe, de forma visível e auditável, o estado das frentes críticas de entrega, validação e produção.

Este monitoramento não substitui GitHub Actions, controle de PR ou revisão humana. Ele consolida sinais operacionais para apoiar decisão, rastreabilidade e governança.

## Fontes mínimas de sinal

| Fonte | Informação mínima | Uso no ReqSys |
|---|---|---|
| Pull Requests | número, título, branch, rascunho, mergeável, estado | controle de entrega |
| Workflows CI/CD | workflow, status, conclusão, commit, data/hora | validação automatizada |
| Gates de produção | autenticação, CORS, JWT, fontes IA, logs, auditoria | bloqueio de produção |
| Issues operacionais | GovBI IA, Dashboard Analítico, Planner, Pipeline | backlog rastreável |
| Validação pública | rota, status, evidência, artifact | smoke operacional |

## Estados canônicos

| Estado | Significado | Ação recomendada |
|---|---|---|
| `verde` | CI ou gate aprovado | pode avançar para próxima etapa |
| `amarelo` | pendência não bloqueante | revisar antes de promover |
| `vermelho` | falha técnica ou funcional | corrigir antes de seguir |
| `bloqueado` | risco de produção, conflito ou gate crítico | impedir merge ou deploy |
| `desconhecido` | sinal indisponível ou não coletado | revalidar fonte |

## Regras operacionais

1. PR em draft nunca é considerado pronto para merge, mesmo com CI verde.
2. CI verde é condição necessária, mas não suficiente, para merge.
3. Falha em gate crítico deve classificar a frente como `bloqueado`.
4. Todo registro deve possuir identificador de correlação, origem, data/hora e severidade.
5. O frontend não deve receber credenciais, payloads sensíveis ou dados pessoais.
6. O painel deve permitir drill-down por frente, PR, workflow e gate.
7. Histórico de mudanças deve ser preservado para auditoria.

## Contrato mínimo sugerido

Campos obrigatórios:

- identificador de correlação;
- data/hora da coleta;
- ambiente;
- estado geral;
- quantidade de bloqueios;
- quantidade de pendências;
- lista de itens monitorados;
- tipo do item;
- referência do item;
- título;
- estado;
- severidade;
- origem;
- detalhes técnicos mascarados.

## UI mínima recomendada

- Card `PRs ativos`.
- Card `CI/CD`.
- Card `Gates de produção`.
- Card `GovBI IA`.
- Card `Dashboard Analítico`.
- Card `Planner`.
- Card `Validação pública`.
- Tabela analítica com filtros por estado, severidade, frente, ambiente e data.
- Deep link preservando filtros do analítico.

## Testes mínimos

- Teste unitário do classificador de estado.
- Teste de contrato do payload consolidado.
- Teste de mascaramento de campos sensíveis.
- Teste de renderização responsiva do painel.
- Smoke test validando que falha crítica aparece como bloqueio.

## Definition of Done

- API ou mock canônico versionado.
- Painel mínimo navegável.
- Drill-down analítico com filtros preservados.
- CI validando contrato, segurança e responsividade.
- Evidência publicada como artifact.
- Documentação e changelog atualizados.

Refs: #33
