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
