# GitHub → Teams: SLO verificável por evidência real

## Contexto

Em 26/10/2026 a issue #1576 informou 74,9% em 10.464 execuções e 2.626 não-sucessos. O cálculo anterior tratava a conclusão do workflow `teams-commit-notification.yml` como recibo de entrega. Entretanto o workflow contém o watchdog agendado do locator e pode terminar com sucesso quando a etapa de envio foi ignorada.

Evidências diretas: run #40422094111 (`success`, envio `skipped`); falhas de envio #37391222176 (HTTP 401), #37390072355 (owner Flow Bot ausente), #37300691739 (HTTP 405); run #40220566988 (`push` real com envio e readback pontual no Teams). Nenhuma prova cobre todas as entregas na janela de 30 dias.

## Requisito 1 — sem confundir execução com entrega

- Calcular separadamente o proxy de execução dos eventos candidatos `push` e `workflow_run`.
- Excluir `schedule` (watchdog) e `workflow_dispatch` (operações ambíguas) do denominador candidato, mantendo suas contagens rastreáveis.
- Contabilizar `success`, `failure`, `timed_out`, `cancelled`, `skipped` e outros resultados separadamente.
- Falha de workflow não é automaticamente falha de entrega e sucesso de workflow não é automaticamente entrega.
- Preservar o identificador da execução, SHA, janela e deduplicação em paginação, sem reclassificar cancelamentos como defeitos sem evidência.

## Requisito 2 — SLO de entrega exige recibo independente

- Publicar `delivery_state=unverified` e taxa de entrega nula enquanto não houver confirmação independente por commit/correlation_id no Microsoft Teams.
- Publicar proxy de conclusão sob um nome explícito; orçamento de erro do proxy não pode ser exibido como orçamento real de entrega.
- Não encerrar a issue #1576 automaticamente com base em proxy, CI verde ou HTTP 2xx isolado.
- Manter falhas reais de transporte/autenticação visíveis; não remover fail-closed, não alterar segredos, webhook nem ambiente de produção.

## Requisito 3 — prevenção e validação

- Executar casos positivo, negativo, cancelamento, watchdog, paginação/deduplicação e erro de dados.
- Incluir os testes no workflow `Workflow Regression Contracts`; uma mutação que restaure auto-fechamento por proxy deve quebrar o contrato preventivo.
- Para recuperar o serviço, executar envio real com correlation_id, prova de chegada no destino e readback independente no mesmo SHA/ambiente; somente então avaliar a janela operacional e o orçamento real.

## Critérios de aceite

1. Watchdog `schedule` não entra no proxy candidato e continua visível.
2. Sucesso `push` sem recibo mantém `delivery_state=unverified`.
3. Falha, cancelamento e skipped são categorias distintas; dados inválidos falham fechado.
4. Duplicata de mesmo run ID não dobra o denominador e janela antiga não entra.
5. Workflow SLO não executa `gh issue close` e registra falta de readback.
6. Testes `tests/test_teams_notification_slo_metrics.py` e verificador `scripts/validate_workflow_regression_contracts.py` aprovados no HEAD.
7. Pre-PR, demais CI e revisão atendidos antes de integração; nenhum deploy/merge por esta alteração sem gates.
8. Não declarar 99% de entrega nem certificação operacional enquanto não houver amostra de recibos independentes.
9. Custo adicional R$ 0,00, Docker ausente, segredos e dados existentes preservados.
