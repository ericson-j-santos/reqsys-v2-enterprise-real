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

## Critérios de aceite

- mensagem enviada aparece como `ENVIADO` com HTTP, canal, latência e correlação;
- falha aparece em `FALHA` e na DLQ;
- retentativa bem-sucedida remove o item da DLQ;
- e-mail/ID de destino não aparece integralmente na API;
- histórico legado continua visível;
- nenhuma alteração de banco existente é destrutiva.
