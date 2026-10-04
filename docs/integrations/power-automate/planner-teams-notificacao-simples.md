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

Os IDs do Team/canal são resolvidos e passados pelo instalador — não fazem
parte do schema dinâmico da ação nesse ponto; só `poster` e `location` são
seletores fixos.

**Formato dos parâmetros na definição do fluxo**: `body/messageBody`,
`body/recipient/groupId`, `body/recipient/channelId` — caminho achatado com
prefixo `body/`, não um objeto `recipient: {...}` aninhado. A API de
gerenciamento de fluxos aceita e ecoa a versão aninhada de volta na mesma
resposta do `PATCH`, mas **não é isso que fica persistido** — uma leitura
logo depois mostra o parâmetro revertido, e o designer do Power Automate
mostra o campo "Cartão Adaptável" vazio. Confirmado em DEV: só o formato
achatado sobrevive a um "Salvar" real no designer.

## Filtro de tarefas de teste automatizado

Suítes de E2E recorrentes (fora do ReqSys) criam tarefas no plano `WSJF DEV`
com o prefixo `REQSYS-E2E-` para testar a sincronização Planner→Excel. Sem
filtro, cada rodada delas dispararia uma notificação real no Teams —
confirmado: uma dessas tarefas notificou sozinha durante os testes deste
fluxo. A ação `Notificar_Teams` fica dentro de uma condição
(`Ignorar_tarefas_de_teste_automatizado`) que bloqueia qualquer título
começando com esse prefixo (`startsWith`, sem diferenciar maiúsculas).

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

Cada um posta um Adaptive Card operacional no canal escolhido: título da tarefa em destaque, `Progresso`, `Vencimento`, ID da tarefa como metadado secundário e ação `Abrir no Planner`. O ID bruto do plano não é exibido no cartão.

## Reconciliação de drift no runtime DEV

O fluxo contínuo de aceite consulta os dois cloud flows no Dataverse antes da prova. Se o `body/messageBody` de `Notificar_Teams` divergir do contrato versionado, atualiza somente esse campo usando o `@odata.etag` corrente, relê o flow e valida o cartão observado. Destinatário, referências de conexão e demais ações são preservados.

A prova de runtime não considera mais suficiente apenas encontrar a mensagem: o attachment do Teams é lido via Microsoft Graph e deve comprovar o cartão corrente, inclusive a ausência dos campos legados `Plano`/`Percentual` e o link `Abrir no Planner` apontando para a tarefa criada no próprio run.

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
