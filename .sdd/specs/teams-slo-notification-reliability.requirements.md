# Teams SLO Notification Reliability — Requisitos

## Contexto
A issue #1576 registra o SLO GitHub → Teams abaixo da meta. Nas execuções recentes, dois runs de `push` foram cancelados antes da criação de qualquer job durante uma rajada de atualizações em `main`, enquanto o monitor de SLO contabiliza toda conclusão diferente de `success` como falha. O envio em `push` também usava `continue-on-error`, podendo ocultar uma falha real de entrega no resultado global do workflow.

## Requisito 1 — não descartar pushes pendentes
Cada evento elegível de `push` em `main` deve poder chegar ao job de notificação sem ser substituído por outro evento apenas por compartilhar a mesma chave de concorrência.

## Requisito 2 — falha de entrega observável
Se o gateway de Teams não confirmar a entrega, a etapa `Enviar notificação` deve falhar e a conclusão do workflow deve permanecer visivelmente degradada, sem `continue-on-error` para `push`.

## Requisito 3 — preservar rastreabilidade
Entregas confirmadas devem continuar registrando HTTP aceito e `correlation_id`. A correção não altera segredos, destinatários nem infraestrutura externa.

## Requisito 4 — recuperação exige evidência nova
A implementação e os testes de contrato não significam recuperação do SLO. A issue #1576 deve permanecer aberta até uma medição posterior, vinculada ao código integrado, demonstrar taxa de sucesso >= 99%, orçamento de erro >= 0 e ausência de novas falhas relevantes.

## Critérios de aceite (Acceptance Criteria)
1. O workflow `teams-commit-notification.yml` não contém bloco `concurrency` que serialize/substitua notificações de `main`.
2. A etapa `Enviar notificação` não contém `continue-on-error`.
3. YAML, self-test do gateway e testes existentes passam no gate de contrato.
4. O Pre-PR Readiness passa no HEAD exato e com `behind_by=0` antes da abertura da PR.
5. Após integração, uma sequência controlada de pelo menos três eventos elegíveis deve produzir jobs executados sem `cancelled` pré-job; cada entrega confirmada deve registrar HTTP 2xx e `correlation_id` próprio.
6. Mesmo com o E2E do item 5 verde, recuperação só pode ser declarada após nova execução do monitor `Teams Notification SLO` satisfazer a meta e o orçamento definidos no requisito 4.

## Evolução de metodologia — 26/10/2026

A inspeção do HEAD `0f212b8ca096ed01e2f1a03405dee0de38fa0a38` identificou que `teams-notification-slo.yml` contava `schedule` (monitor de locator PC24x7) e `workflow_dispatch` como se fossem envios. Também associava conclusão `success` a entrega mesmo quando o job `Enviar notificação` não executou (run 40422094111). Uma execução `workflow_run` pode ser suprimida por política de admissão mesmo que o workflow termine verde. A issue #1576 apresentou taxa histórica de 74,9% em 10.464 execuções, número de conclusão de Actions e não recibos Teams. Logs anteriores comprovam HTTP 401 e owner Flow Bot ausente, mas não justificam atribuir todas as falhas a essas causas.

### Critérios adicionais do monitor

7. Excluir `schedule` e `workflow_dispatch` do denominador de execuções candidatas; preservar seu volume separado em `all_events` e `excluded_non_candidate_runs` no schema `2.0.0`. Não usar exclusão como prova de recuperação.
8. Distinguir explicitamente `failure`, `cancelled`, `timed_out`, `skipped`, `neutral` e demais conclusões; manter todos os não-success identificados no indicador de execução, sem dizer que cada um é tentativa de entrega falha.
9. Expor taxa de conclusão dos workflows como métrica auxiliar; manter `delivery_state=unverified`, `delivery_verified=false` e sem taxa/orçamento efetivo de entrega até existir leitor independente do Teams com correlação por mensagem, SHA e ambiente.
10. Não fechar automaticamente o incidente #1576 com sucesso de Actions ou HTTP 2xx. Na falta de amostra candidata, informar `workflow_execution_state=insufficient_data` e `state=insufficient_data`, mantendo `delivery_state=unverified`; preservar o gate de alerta de dados mínimos.
11. Executar `tests/test_teams_notification_slo_semantics.py` e `tests/test_teams_notification_slo_metrics.py` na suíte `Workflow Regression Contracts`, com cenário positivo, controle negativo do filtro antigo, IDs únicos para eventos distintos e repetição idempotente, além de `READY_FOR_PR=passed` no HEAD da branch atual antes da PR.
12. Após integração governada, obter recibos independentes de mensagens efetivamente recebidas, validar supressões legítimas, observação de 30 dias, SLO >=99% e orçamento >=0 para avaliar recuperação; até então, estado parcial e issue aberta. Não alterar destinatários, credenciais, produção ou recursos pagos neste incremento.
