# Teams Notification Control Center

## Objetivo

Transformar a rota de UI `/notificacoes` no ponto central de acompanhamento das mensagens Microsoft Teams do ReqSys.

## Escopo implementado

- consolidação de mensagens de commits, CI, logs, HITL, manuais e gateway;
- dashboard com pendentes, processando, enviados, falhas, taxa de sucesso e latência;
- fila governada com envio imediato ou processamento posterior;
- DLQ com retentativa limitada e auditável;
- `correlation_id` em todas as mensagens governadas;
- destinatário mascarado e hash SHA-256 na resposta da API;
- preservação do conteúdo/destino bruto somente na tabela interna necessária à retentativa;
- histórico existente reaproveitado de `integracao_log`, sem migração destrutiva;
- atualização automática da tela existente a cada 30 segundos.

## Endpoints

Base: `/v1/teams-gateway/notificacoes`

| Método | Endpoint | Finalidade |
|---|---|---|
| GET | `/dashboard` | KPIs e cobertura por origem |
| GET | `/fila` | Fila central e histórico legado consolidado |
| GET | `/dlq` | Falhas reprocessáveis da fila governada |
| GET | `/logs` | Auditoria dos envios realizados pelo gateway |
| POST | `/enfileirar` | Criar e opcionalmente enviar uma mensagem governada |
| POST | `/fila/processar/{id}` | Processar item pendente |
| POST | `/dlq/reprocessar/{id}` | Reexecutar item da DLQ |

## Segurança

- leitura exige usuário autenticado;
- escrita e reprocessamento exigem administrador;
- tokens, secrets, URLs de webhook e cabeçalhos de autorização são removidos de metadata persistida;
- API nunca retorna destino bruto nem texto integral da mensagem;
- não são persistidos access tokens ou webhook URLs no item da fila.

## Operação

A tabela `teams_notification_queue` é criada no startup pelo mecanismo atual de `Base.metadata.create_all`.

O painel reaproveita os eventos `teams_gateway` existentes em `integracao_log`. Eventos criados pela fila central são identificados por `central_notification_event_id` para evitar contagem duplicada.

## Monitoramento contínuo

O workflow `.github/workflows/teams-notification-control-center-smoke.yml` executa:

- a cada hora, no minuto 17;
- após mudanças relevantes integradas à `main`;
- manualmente, por `workflow_dispatch`.

Para DEV, HML e PROD, o monitor valida:

1. disponibilidade de `/health`;
2. existência das quatro rotas do Control Center;
3. proteção das rotas sem autenticação, esperando HTTP 401 ou 403;
4. contrato autenticado quando o login demo estiver habilitado ou existir token governado;
5. envelope da API e campos mínimos do dashboard;
6. geração de evidência JSON com SHA-256.

Estados operacionais:

| Estado | Significado |
|---|---|
| `healthy` | disponibilidade, proteção e contrato autenticado aprovados |
| `degraded` | rotas disponíveis e protegidas, mas sem credencial para validar o conteúdo autenticado |
| `failed` | indisponibilidade, rota ausente, proteção incorreta, contrato inválido ou canário não entregue |

Tokens opcionais podem ser configurados sem exposição nos logs:

- `REQSYS_TEAMS_SMOKE_BEARER_TOKEN_DEV`;
- `REQSYS_TEAMS_SMOKE_BEARER_TOKEN_HML`;
- `REQSYS_TEAMS_SMOKE_BEARER_TOKEN_PROD`.

A execução manual permite `require_authenticated=true` para tornar a ausência de autenticação bloqueante. A opção `send_canary=true` envia uma mensagem real, exige token administrativo e valida `PENDENTE → PROCESSANDO → ENVIADO` por `correlation_id`.

O canário real não é executado pelo agendamento horário, evitando ruído recorrente no Teams.

Artifacts:

- `teams-control-center-smoke-{ambiente}`: evidência individual, retenção de 30 dias;
- `teams-control-center-smoke-summary`: consolidação executiva, retenção de 90 dias.

Falhas do workflow acionam automaticamente `Notify Teams - ReqSys Logs`, produzindo Adaptive Card sanitizado com link para a execução.

## Critérios de aceite

- mensagem enviada aparece como `ENVIADO` com HTTP, canal, latência e correlação;
- falha aparece em `FALHA` e na DLQ;
- retentativa bem-sucedida remove o item da DLQ;
- e-mail/ID de destino não aparece integralmente na API;
- histórico legado continua visível;
- nenhuma alteração de banco existente é destrutiva;
- smoke DEV/HML/PROD produz evidência navegável;
- falha do painel gera mensagem de acompanhamento no Teams.
