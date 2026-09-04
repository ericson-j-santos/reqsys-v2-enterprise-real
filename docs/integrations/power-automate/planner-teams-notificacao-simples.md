# Planner → Teams: notificação de mudanças

## Objetivo

Avisar no Teams quando uma tarefa é criada ou concluída num plano do Planner,
reaproveitando o webhook do Teams já configurado e validado
(`TEAMS_NOTIFICATIONS_WEBHOOK_URL`), sem depender de um Team/canal dedicado.

## Perfil

`planner_teams_notificacao_simples`

Arquitetura:

`Planner (trigger nativo) → Power Automate → HTTP POST no webhook Teams já existente`

## Fonte oficial

O Planner é a fonte oficial. O fluxo é unidirecional: nenhuma escrita no
Planner (nenhuma operação `UpdateTask` é permitida).

## Endpoints

### Contrato

`GET /v1/hub-lowcode/planner-teams-notify/contract`

### Validação sem implantação

`POST /v1/hub-lowcode/planner-teams-notify/validate`

### Provisionamento

`POST /v1/hub-lowcode/planner-teams-notify/deploy`

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
vencimento) no webhook do Teams via ação HTTP nativa — sem usar o conector
Teams (não há Team/canal provisionado sobre o grupo do plano).

## Segurança

- somente DEV neste incremento;
- webhook do Teams é injetado pelo backend a partir de
  `TEAMS_NOTIFICATIONS_WEBHOOK_URL` — o cliente (frontend) não escolhe o
  destino;
- nenhuma credencial no bundle;
- fluxos importados parados por padrão; ativação posterior é explícita;
- nenhuma operação `UpdateTask` é permitida.

## Limite operacional atual (o que falta para uso real)

- Sem interface própria ainda: instalação hoje só via chamada direta aos
  endpoints acima (mesmo padrão usado para validar o WSJF antes de ter tela).
- Não testado contra o tenant real ainda — pendente de decisão sobre quando
  fazer o primeiro deploy real em DEV.
- Caminho de volta (responder/anexar arquivo no Teams e refletir no Planner)
  é explicitamente fora de escopo deste incremento — ver conversa que
  motivou este documento para o racional da divisão em fases.
