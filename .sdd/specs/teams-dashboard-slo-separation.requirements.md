# Teams Dashboard — separação SLO de entrega x watchdog do locator

## Contexto evidenciado

O workflow `Teams Commit Notification` executa dois papéis diferentes:

1. entrega real de notificações em eventos `push` e `workflow_run`;
2. watchdog periódico do locator PC24x7 em `schedule`.

Quando o locator assinado está ausente, o watchdog falha fechado — comportamento
correto para evidenciar degradação do runtime canônico. Porém o dashboard
`Teams Notification Dashboard` contabilizava todos os runs do workflow como
se fossem tentativas de entrega. Isso misturava indisponibilidade do locator
com falha de entrega, mesmo quando o webhook governado de contingência seguia
entregando corretamente.

Em 21/10/2026:
- o schedule `39573219070` falhou com `no_valid_fresh_signed_locator`;
- o workflow_run `39574202403` entregou com sucesso via `webhook_fallback`;
- o dashboard publicado reportava 6.858 runs, 1.922 falhas e SLO 71,97%;
- o artefato Pages `12333847929` continha `generated_at=2026-10-21T08:50:17Z`;
- após deploy governado `39575431249`, o retry do monitor `39556957593`
  passou e fechou automaticamente a issue #3002.

## Objetivo

Separar semânticas operacionais sem esconder falhas:

- entrega real ao Teams continua medida por SLO;
- watchdog do locator continua fail-closed e visível;
- falha do locator não reduz artificialmente o SLO de entrega quando a
  contingência está operacional;
- o dashboard público é revalidado imediatamente após publicação Pages;
- incidentes automáticos não geram ruído de governança de Issues.

## Requisito 1 — eventos elegíveis para SLO de entrega

O dashboard deve considerar como tentativas de entrega somente runs de
`Teams Commit Notification` com evento:

- `push`;
- `workflow_run`.

Runs `schedule` não são entregas e não entram em:
- `total_runs`;
- `successful_runs`;
- `failed_runs`;
- `success_rate_percent`;
- error budget;
- duração média da entrega;
- falhas consecutivas de entrega;
- amostra de certificação de entrega.

## Requisito 2 — watchdog do locator permanece visível

Runs `schedule` devem continuar sendo coletados separadamente como saúde do
locator/watchdog.

A evidência pública deve incluir, no mínimo:
- total de runs do watchdog;
- sucessos;
- falhas;
- taxa de sucesso;
- falhas consecutivas recentes.

O workflow `Teams Commit Notification` não deve deixar de falhar quando o
locator está inválido/expirado. A correção é de classificação da métrica, não de
relaxamento do gate.

## Requisito 3 — revalidação pós-Pages

`Teams Dashboard Availability Monitor` deve executar automaticamente quando
`Deploy ReqSys Pages Composite` terminar com `success`.

A execução por `workflow_run` deve:
- ignorar deploys falhos/cancelados;
- preservar schedule periódico;
- preservar workflow_dispatch manual;
- continuar verificando HTTP, contrato e frescor de `data.json`;
- fechar o incidente automaticamente apenas quando o monitor observar estado
  `healthy`.

## Requisito 4 — incidente operacional governado

Issues automáticas do monitor devem usar o marcador:

`<!-- reqsys-operational-panel -->`

Esse marcador é o contrato canônico de `scripts/validate_issue_governance.py`
para Issues mantidas por automação/bot.

Se uma issue já estiver aberta, o monitor deve atualizar o corpo com o marcador
e o estado atual antes de adicionar o comentário de atualização.

## Requisito 5 — sem falso positivo

Os testes devem comprovar que:

1. `schedule` não é elegível para SLO de entrega;
2. `push` e `workflow_run` continuam elegíveis;
3. o watchdog continua fail-closed;
4. o monitor pós-Pages só roda após conclusão `success`;
5. o incidente gerado passa pelo contrato de painel operacional;
6. nenhum `continue-on-error` transforma falha real em sucesso;
7. nenhum novo workflow é criado.

## Requisito 6 — fronteira operacional

Este incremento:
- não altera segredos;
- não altera Teams webhook;
- não altera destino do Teams;
- não recupera artificialmente o locator;
- não toca HML/STG/PROD;
- não altera custos;
- não publica Pages por si só;
- não fecha issue sem prova do monitor.

## Critérios de aceite

1. Pre-PR Readiness fica verde no HEAD atual e `behind_by=0`.
2. Testes direcionados comprovam separação dos eventos.
3. `Teams Commit Notification` mantém locator watch fail-closed.
4. Dashboard gera métricas separadas de entrega/watchdog.
5. Availability Monitor contém gatilho pós-Pages e guarda de sucesso.
6. Issue operacional produzida satisfaz a governança sem comentário de correção.
7. CI principal e gates de segurança ficam verdes.
8. Custo adicional = R$ 0,00.

## Evolução #1358 — painel persistente e recibo independente (05/11/2026)

A execução 41984951174 (main 863a316cb63ec11908bb86a28d5212937a145689)
publicou 54,24% para 1.357 execuções do workflow misturando eventos de
notificação e monitor de locator. A conclusão de GitHub Actions é um proxy:
não comprova o recebimento da mensagem no Teams. A disponibilidade do painel
também possui monitor próprio, com 22 runs e taxa de 54,55% em 7 dias.

### Requisitos adicionais

7. O painel de certificação da issue #1358 seleciona para o proxy de execução
   somente eventos de candidatos push e workflow_run, e nunca schedule ou
   workflow_dispatch. O monitor de disponibilidade do dashboard é independente,
   mantém suas falhas e não perde a regra de frescor.
8. O relatório mantém schema_version 2.0.0, janelas 7/30 dias, histórico,
   meta de 99%, denominadores e estados originais, adicionando os campos
   delivery_state=unverified, delivery_verified=false, delivery_success_rate_percent=null
   e metric_kind=workflow_execution_proxy_not_delivery.
9. Nem workflow success, HTTP 2xx, contingência, cache saudável ou valores
   positivos do proxy concedem provisional_gold/gold_certified sem readback
   independente no Teams por mensagem, SHA e ambiente. Na falta de comprovação,
   a certificação permanece quality_blocked com causa explícita. Não alterar
   o limiar 99%, a integridade do monitor nem o gate fail-closed do locator.
10. Regressão real executa o Python do workflow com dados sintéticos: cenário
    positivo de proxy 100% sem certificação, falha de schedule excluída do
    denominador do proxy, falha workflow_run incluída, falha do monitor incluída,
    replay sem divergência e HTML/Markdown com aviso de entrega não verificada.
11. Após integração governada, reexecutar o publicador da issue na main vigente,
    comparar artefato SHA e a publicação, e exigir leitor independente Teams
    antes de declarar recuperação. A publicação Pages continua dependente de
    autorização própria e nunca é consequência deste ajuste.
12. Custo incremental zero; não alterar segredos, destinatários ou ambientes
    produtivos. Evidenciar READY_FOR_PR no SHA, CI/contratos e TODO Global.
