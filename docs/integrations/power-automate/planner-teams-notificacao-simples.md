# Planner → Teams: notificação de mudanças

## Objetivo

Avisar num canal do Teams quando uma tarefa é criada ou concluída num plano
do Planner.

## Perfil

`planner_teams_notificacao_simples`

Arquitetura:

`Planner (trigger nativo) → Power Automate → conector Teams (Post card in a chat or channel, Post as: Flow bot)`

## Fonte oficial

O Planner é a fonte oficial. O fluxo é unidirecional: nenhuma escrita no
Planner (nenhuma operação `UpdateTask` é permitida).

## Por que não um webhook genérico

A primeira versão deste perfil tentou reaproveitar um webhook do Teams já
configurado (`TEAMS_NOTIFICATIONS_WEBHOOK_URL`). Verificação real em DEV
(`GET /v1/teams-gateway/status`) mostrou que nenhum canal de saída
automática estava de fato configurado nesse backend — nem webhook, nem bot,
nem flow_bot. O grupo do plano também não tinha um Team provisionado
(`resourceProvisioningOptions` citava `Team`, mas `GET .../groups/{id}/team`
devolvia `NotFound` — provisionamento nunca tinha sido concluído).

A correção usa o conector Teams real (`shared_teams`), operação
`PostCardToConversation` ("Post card in a chat or channel"), com
`poster: "Flow bot"` e `location: "Channel"` — os mesmos valores fixos que a
UI de Workflows do Teams usa (`Canal → Workflows → "Postar num canal quando
um webhook for recebido"` é só uma forma de chegar nesse mesmo tipo de
fluxo; a operação em si é conector nativo, não fica descontinuada junto com
os conectores clássicos "Incoming Webhook"). Confirmado com uma chamada real
via essa mesma operação: a mensagem chegou no canal de verdade.

Os IDs do Team/canal (`recipient.groupId`/`recipient.channelId`) são
resolvidos e passados pelo instalador — não fazem parte do schema dinâmico
da ação nesse ponto; só `poster` e `location` são seletores fixos.

## Endpoints

### Contrato

`GET /v1/hub-lowcode/planner-teams-notify/contract`

### Validação sem implantação

`POST /v1/hub-lowcode/planner-teams-notify/validate`

### Provisionamento

`POST /v1/hub-lowcode/planner-teams-notify/deploy`

Payload inclui `teams_team_id`, `teams_channel_id` e `teams_connection_id`
(a conexão Teams autorizada no Power Automate do ambiente — item
interativo, só o usuário consegue autorizar) além dos campos já usados no
WSJF (`environment_id`, `group_id`, `plan_id`, `planner_connection_id`).

Mesma arquitetura provada em `wsjf_planner_excel_provisioning.py` (ver
[wsjf-planner-excel-simples.md](wsjf-planner-excel-simples.md)): a API de
gerenciamento de fluxos do Power Automate não aceita credencial app-only, só
token delegado do usuário (`X-Power-Automate-Token`, adquirido via MSAL no
frontend); a idempotência busca por `displayName` a cada execução e faz
`PATCH` no id real encontrado, ou `POST` para criar quando não existe — não
há upsert por um id escolhido pelo cliente nessa API.

## Dois fluxos, dois eventos

1. `ReqSys - Notificar Teams (Tarefa criada no Planner)` — trigger
   `OnNewTask_V3` do conector Planner.
2. `ReqSys - Notificar Teams (Tarefa concluída no Planner)` — trigger
   `OnCompleteTask_V3` do conector Planner.

Cada um posta um Adaptive Card simples (título da tarefa, plano, percentual,
vencimento) no canal escolhido.

## Segurança

- somente DEV neste incremento;
- nenhuma credencial no bundle — apenas os ids do Team/canal e o nome da
  conexão Teams já autorizada;
- fluxos importados parados por padrão; ativação posterior é explícita;
- nenhuma operação `UpdateTask` é permitida.

## Limite operacional atual (o que falta para uso real)

- Sem interface própria ainda: instalação hoje só via chamada direta aos
  endpoints acima (mesmo padrão usado para validar o WSJF antes de ter tela).
- Caminho de volta (responder/anexar arquivo no Teams e refletir no Planner)
  é explicitamente fora de escopo deste incremento — ver conversa que
  motivou este documento para o racional da divisão em fases.
