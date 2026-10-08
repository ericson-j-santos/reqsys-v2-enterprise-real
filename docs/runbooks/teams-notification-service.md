# Runbook Operacional — GitHub → Microsoft Teams

## 1. Escopo

Serviço responsável por notificar commits da `main` no Microsoft Teams, executar canário periódico, calcular SLO, publicar dashboard e monitorar sua disponibilidade pública.

## 2. Objetivos operacionais

| Indicador | Meta |
|---|---:|
| Disponibilidade de entrega | ≥ 99,0% em 30 dias |
| RTO para falha de entrega | 4 horas |
| RTO para dashboard indisponível | 6 horas |
| RPO das evidências | 24 horas |
| Frescor máximo do dashboard | 48 horas |
| Retenção de evidências | 90 dias |

## 3. Componentes

- `.github/workflows/teams-commit-notification.yml`
- `.github/workflows/teams-commit-notification-contract.yml`
- `.github/workflows/teams-notification-observability.yml`
- `.github/workflows/teams-notification-slo.yml`
- `.github/workflows/teams-notification-dashboard.yml`
- `.github/workflows/teams-dashboard-availability-monitor.yml`
- `tools/geradores/teams_graph_gateway_autocontido.py`
- `ops-dashboard/teams-notification/index.html`

## 4. Classificação automática de incidentes

| Código | Sintoma | Causa provável | Ação principal |
|---|---|---|---|
| `CFG-001` | Secret ausente | `TEAMS_WEBHOOK_URL` não configurado | Cadastrar secret no repositório |
| `LOC-001` | `SIGNED_LOCATOR_BLOCKED` | Locator PC24x7 expirado ou runtime físico indisponível | Confirmar fallback governado e recuperar o PC24x7 |
| `FLOW-001` | `nenhum flow_bot_owner ativo` | Owner do Power Automate ausente no runtime PC24x7 | Executar `Teams Commit Notification` com `operation=reconcile-flow-bot` |
| `AUTH-001` | HTTP 401/403 | URL exige autenticação ou credencial inválida | Substituir pela URL do Workflows/Webhook aceita pelo canal |
| `RATE-001` | HTTP 429 | Limite temporário do endpoint | Aguardar retry automático; validar volume |
| `ENDP-001` | HTTP 404/410 | Endpoint removido ou expirado | Gerar nova URL e atualizar secret |
| `NET-001` | Timeout/5xx | Falha transitória de rede ou serviço | Executar novamente e acompanhar status Microsoft |
| `PAGE-001` | Dashboard HTTP diferente de 200 | Pages desabilitado ou deploy falhou | Validar Pages com Source GitHub Actions |
| `DATA-001` | `data.json` inválido | Falha no build ou contrato alterado | Reexecutar dashboard e revisar schema |
| `FRESH-001` | Dados acima de 48h | Agendamento ou publicação interrompidos | Reexecutar SLO e dashboard |
| `SLO-001` | Taxa abaixo de 99% | Falhas recorrentes de entrega | Congelar incrementos e tratar causa dominante |

## 5. Procedimento de resposta

### P0 — Entrega totalmente indisponível

1. Abrir a execução mais recente de `Teams Commit Notification`.
2. Identificar o código de causa pela tabela deste runbook.
3. Confirmar se o secret existe sem expor seu valor.
4. Executar `workflow_dispatch` com mensagem de teste.
5. Validar HTTP 2xx, `success=true` e `correlation_id`.
6. Confirmar visualmente a mensagem no Teams.
7. Registrar evidência na issue e fechar somente após duas execuções verdes consecutivas.

O workflow prioriza o locator assinado e o Teams Messaging Gateway. Se o locator falhar antes de qualquer tentativa de envio, ele seleciona automaticamente o webhook governado de contingência, registra `delivery_route=webhook_fallback` e mantém o run verde somente após confirmação HTTP 2xx. A contingência não substitui a recuperação do PC24x7 e não é tentada após uma chamada ambígua ao gateway, evitando duplicidade.

Se o locator estiver válido, mas o gateway responder que nenhum owner Flow Bot
está ativo, execute manualmente `Teams Commit Notification` com a operação
`reconcile-flow-bot`. O
workflow reutiliza `TEAMS_WEBHOOK_URL`, `TEAMS_WEBHOOK_RECIPIENT` e
`COFRE_ADMIN_JWT` já protegidos no GitHub Environment `development`, cria ou
atualiza o owner de forma idempotente e exige uma entrega real antes de publicar
evidência sanitizada. Valores de segredo não são passados por argumentos nem
gravados no artifact.

Se `COFRE_ADMIN_JWT` estiver expirado, a operação valida `/v1/auth/config` e
obtém uma sessão administrativa efêmera somente quando o próprio runtime
comprovar ambiente DEV, login demo habilitado e papel `admin`. A recuperação é
recusada fora de DEV e o token efêmero nunca integra logs ou artifacts.

### P1 — Dashboard ou métricas indisponíveis

1. Verificar `Teams Notification Dashboard`.
2. Confirmar configuração do GitHub Pages: Source `GitHub Actions`.
3. Validar `index.html` e `data.json`.
4. Executar manualmente o dashboard.
5. Executar `Teams Dashboard Availability Monitor`.
6. Fechar o incidente somente com estado `healthy`.

### P2 — SLO degradado

1. Abrir o artifact mais recente de `Teams Notification SLO`.
2. Aplicar Pareto sobre conclusões e códigos HTTP.
3. Tratar primeiro a causa responsável pela maior parcela das falhas.
4. Reavaliar orçamento de erro após cada correção.
5. Não considerar recuperação com amostra zero.

## 6. Critérios de recuperação

- workflow de envio verde;
- endpoint aceitou a mensagem com HTTP 2xx;
- `correlation_id` registrado;
- rota selecionada registrada como `gateway` ou `webhook_fallback`;
- dashboard HTTP 200;
- `data.json` válido e fresco;
- monitor com estado `healthy`;
- issue de incidente fechada automaticamente;
- duas execuções consecutivas verdes para falhas P0.

## 7. Mudanças administrativas manuais

As seguintes ações não podem ser automatizadas pelo código do repositório:

- cadastrar ou substituir `TEAMS_WEBHOOK_URL`;
- habilitar GitHub Pages com Source `GitHub Actions`;
- confirmar visualmente a mensagem no canal do Teams;
- conceder permissões administrativas do Microsoft Teams/Power Platform.

A reconciliação de um secret já cadastrado com o owner do runtime PC24x7 é
automatizada; criar ou substituir a credencial de origem continua sendo uma
ação administrativa manual.

## 8. Links operacionais

- Actions: `https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions`
- Secrets: `https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/settings/secrets/actions`
- Pages: `https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/settings/pages`
- Dashboard: `https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/`

## 9. Definição de padrão ouro consolidado

O serviço é considerado consolidado quando, durante 30 dias:

- SLO ≥ 99%;
- nenhum incidente P0 permanece aberto além do RTO;
- canário semanal executa sem intervenção;
- dashboard permanece disponível e com dados frescos;
- toda falha produz issue, artifact e classificação de causa;
- recuperação fecha automaticamente o incidente;
- nenhuma credencial é exposta em logs, artifacts ou dashboard.
