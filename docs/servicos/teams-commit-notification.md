# Notificação de commits no Microsoft Teams

## Fluxo

`push em main` → `Teams Commit Notification` → `Teams Gateway autocontido` → webhook do Teams/Workflows.

## Configuração obrigatória

Cadastre no repositório os secrets:

```text
TEAMS_WEBHOOK_URL
TEAMS_WEBHOOK_RECIPIENT
```

`TEAMS_WEBHOOK_URL` deve ser a URL de gatilho HTTP de um fluxo do Power Automate (app Workflows) que receba `{to, title, content, signature, stampDate, correlationId, eventType}`. `TEAMS_WEBHOOK_RECIPIENT` deve ser o e-mail/UPN da pessoa destinatária do fluxo `Chat with Flow bot` 1:1.

`eventType` é sempre `"commit-notification"` para este workflow — o campo existe para permitir que um fluxo de destino compartilhado (ex.: `robo_envia_teamsv2`) diferencie eventos de commit de outros tipos de evento (ex.: aprovação de requisito) e nunca reaproveite acidentalmente um cartão fixo de outro fluxo.

Este é o mesmo contrato de payload usado pela família de fluxos `robo_envia_teams*` já em produção neste tenant — reutilizar um desses fluxos, ou um clone compatível, em vez de criar um schema diferente.

## Política de execução

- `push` em `main`: modo **report-only**. A tentativa de entrega é executada e registrada, mas uma indisponibilidade externa do Power Automate/Teams não invalida o CI do código.
- `workflow_dispatch`: modo **estrito**. A execução falha quando o endpoint não confirma HTTP 2xx e `success=true`.
- `schedule`: canário semanal em modo **estrito**, para evidenciar indisponibilidade real da integração.

O resumo do job registra o resultado real da etapa: `entregue/aceito`, `ignorado` ou `degradado — entrega não confirmada`.

## Validação

Após o merge, execute manualmente o workflow **Teams Commit Notification** usando `workflow_dispatch`. O job somente conclui com sucesso quando:

- os dois secrets existem;
- o gateway passa no `self-test`;
- o endpoint retorna HTTP 2xx;
- o resultado contém `success=true`;
- o resumo registra HTTP e `correlation_id`.

## Contrato de resposta (proteção contra roteamento incorreto)

Se o fluxo de destino ecoar `correlationId` e/ou `eventType`/`type` na resposta HTTP, o gateway (`TeamsGateway._validar_contrato_resposta`, em `tools/geradores/teams_graph_gateway_autocontido.py`) rejeita a chamada (`GatewayError`) quando esses valores não conferem com o que foi enviado. Isso existe especificamente para detectar o caso em que o fluxo processa a chamada como um evento diferente do esperado (por exemplo, roteando para o template estático de aprovação de requisitos em vez do template dinâmico de commit) — nesse caso o CI falha em vez de reportar sucesso silenciosamente. Quando o fluxo não ecoa esses campos (caso do `robo_envia_teamsv2` hoje, que responde apenas `{ok, to, titleLength, ...}`), a validação é tolerante e não bloqueia o envio.

## Segurança

- A URL não é registrada nos logs.
- Os secrets não ficam no código.
- O workflow possui somente permissão `contents: read`.
- Mensagens são construídas sem executar conteúdo proveniente da mensagem do commit.
