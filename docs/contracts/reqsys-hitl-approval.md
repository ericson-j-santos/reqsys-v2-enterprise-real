# ReqSys HITL Approval Orchestrator

## Objetivo

Automatizar a solicitação, notificação e captura de decisões humanas sem atribuir aprovação a bots. O GitHub é a fonte auditável; Teams e e-mail são canais de entrega.

## Criação da solicitação

O workflow `ReqSys HITL Approval Orchestrator` pode ser iniciado por `workflow_dispatch` com:

- título;
- controle/escopo;
- resumo;
- URL GitHub das evidências;
- prazo opcional.

A execução cria uma issue com o marcador `<!-- reqsys-hitl-approval -->` e o label `hitl-approval-request`.

## Notificações

### Teams

O workflow usa `scripts/notify_hitl_approval_teams.py`, o Teams Messaging Gateway existente e a política lógica `hitl-approvers`.

#### Separação entre credenciais e destinatários

- Secrets armazenam somente credenciais técnicas.
- Pessoas, grupos, canais e prioridades ficam na tabela `teams_notification_recipients`.
- `TEAMS_GATEWAY_DESTINO_ID` é aceito somente como fallback de transição quando a política ainda não possui destinatários ativos.
- Enquanto o runtime ainda não expuser o endpoint de políticas e responder HTTP 404, o cliente tenta uma única vez o endpoint legado, somente quando `TEAMS_GATEWAY_DESTINO_ID` estiver configurado.
- O fallback de compatibilidade não é usado para erros de rede, autenticação, validação ou falhas diferentes de HTTP 404.
- Alterar a composição dos aprovadores não exige mudança em secret, workflow, branch ou deploy.

#### Cadastro administrativo

Endpoints protegidos por administração:

```text
GET    /v1/teams-gateway/recipient-policies/recipients
POST   /v1/teams-gateway/recipient-policies/recipients
PATCH  /v1/teams-gateway/recipient-policies/recipients/{id}
DELETE /v1/teams-gateway/recipient-policies/recipients/{id}
```

Exemplo de cadastro:

```json
{
  "politica": "hitl-approvers",
  "nome": "Aprovador de Governança",
  "destino_id": "aprovador@empresa.com",
  "destino_tipo": "chat",
  "prioridade": 10,
  "ativo": true
}
```

#### Modos de entrega

| Modo | Comportamento |
|---|---|
| `all` | envia para todos os destinatários ativos |
| `first_success` | tenta por prioridade até a primeira entrega |
| `channel` | envia uma vez para o primeiro canal/webhook ativo |

O workflow HITL usa `all`. A evidência agrega quantidade configurada, tentada, entregue e falha, sem expor o UPN dos destinatários no artifact agregado.

A falha de notificação produz warning e evidência, mas não derruba o CI. A solicitação continua disponível no GitHub e no pacote de e-mail.

### E-mail

O workflow sempre gera um arquivo MIME `.eml` auditável. O envio SMTP ocorre somente quando estes secrets existem:

- `HITL_EMAIL_FROM`;
- `HITL_EMAIL_TO`;
- `HITL_SMTP_HOST`;
- `HITL_SMTP_PORT`;
- `HITL_SMTP_USERNAME`;
- `HITL_SMTP_PASSWORD`;
- `HITL_SMTP_MODE` (`plain`, `starttls` ou `ssl`).

Credenciais nunca são gravadas em artifacts ou logs.

## Decisão autenticada

A decisão é registrada em comentário na issue:

```text
/approve Evidências revisadas e risco residual aceito.
/reject Evidência insuficiente para assumir responsabilidade formal.
/adjust Incluir assinatura jurídica e evidência real do IdP.
```

Regras:

- justificativa mínima de 10 caracteres;
- ator não pode terminar com `[bot]`;
- permissão GitHub deve ser `write`, `maintain` ou `admin`;
- issue deve possuir `hitl-approval-request`;
- o comentário e a issue formam referências imutáveis.

## Saída

Artifact `reqsys-hitl-decision-<issue>` retido por 90 dias, contendo:

- ator e permissão;
- decisão e justificativa;
- data;
- issue e comentário;
- SHA da origem;
- SHA-256 da solicitação;
- SHA-256 da decisão;
- correlation ID;
- próxima ação permitida;
- `production_touched=false`.

## Efeitos

| Decisão | Estado da issue | Ação automática |
|---|---|---|
| `approve` | fecha com `hitl-approved` | reexecuta somente gates seguros |
| `reject` | fecha com `hitl-rejected` | mantém entrega bloqueada |
| `adjust` | mantém aberta com `hitl-adjustment-requested` | aguarda nova evidência |

A aprovação não altera diretamente a matriz BACEN, não executa deploy e não libera PROD.
