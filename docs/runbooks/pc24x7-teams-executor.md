# PC24x7 — Executor durável da Central de Conversas Teams

## Objetivo

Conectar a Central de Conversas de IA ao PC24x7 sem depender da sessão interativa do operador.
O PC24x7 atua como consumidor durável; o ReqSys continua sendo o sistema autoritativo da conversa.

```text
Chat / Issue / ReqSys Coordinator
        ↓
producer pc24x7_teams_queue.py enqueue
        ↓
fila durável em volume local
        ↓
teams-24x7-worker
        ↓
POST /v1/teams-gateway/ai-conversations
        ↓
ReqSys → provedor IA → Azure Bot → Teams
        ↓
evidência sanitizada + done/retry/quarantine
```

## Escopo

- somente DEV;
- não promove TEST/PROD;
- não armazena segredo dentro do job;
- service token é lido de arquivo montado somente-leitura;
- a fila usa SHA-256 do payload de negócio para deduplicação;
- cada job possui `correlation_id`;
- retry exponencial e quarentena após o limite configurado.

## Pré-requisito único

Criar um arquivo local legível somente pela conta do serviço contendo um `X-Service-Token`
com escopo **apenas** `teams_gateway:ai_conversations`.

Exemplo de caminho Windows/WSL:

```text
C:/ProgramData/ReqSys/secrets/teams-ai-service-token.txt
```

Nunca versionar, imprimir ou anexar esse arquivo.

Defina no `.env` do host:

```text
REQSYS_API_BASE_URL=https://reqsys-api-dev.fly.dev
REQSYS_API_SERVICE_TOKEN_FILE=C:/ProgramData/ReqSys/secrets/teams-ai-service-token.txt
PC24X7_TEAMS_MAX_ATTEMPTS=5
```

## Subir o worker

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.dev.yml \
  -f docker-compose.pc24x7-teams.yml \
  up -d teams-24x7-worker
```

O container usa `restart: unless-stopped`, portanto volta automaticamente quando o Docker volta.

## Enfileirar o primeiro turno DEV

```bash
python scripts/pc24x7_teams_queue.py \
  --root ./var/pc24x7-teams \
  enqueue \
  --provider gemini \
  --model gemini-2.5-flash \
  --titulo "ReqSys Teams E2E DEV" \
  --mensagem "Executar primeiro turno E2E DEV e aguardar continuidade pelo Adaptive Card."
```

Executar novamente o mesmo payload não cria segundo job enquanto o primeiro estiver
`pending`, `processing` ou `done`.

## Estados

| Diretório | Significado |
|---|---|
| `pending` | aguardando consumo/retry |
| `processing` | claim atômico em andamento |
| `done` | chamada ReqSys concluída |
| `quarantine` | limite de tentativas esgotado |
| `evidence` | evidência sanitizada por tentativa |

## Evidência mínima para considerar sucesso

O arquivo em `evidence/` deve conter simultaneamente:

```json
{
  "status": "done",
  "conversation_id": "<não vazio>",
  "teams_delivered": true,
  "teams_channel": "bot",
  "payload_sha256": "<sha256>",
  "correlation_id": "<não vazio>",
  "secret_value_exposed": false
}
```

`done` sem `teams_delivered=true` não fecha o E2E.

## Retomada e falhas

Falha de rede, timeout, token inválido ou erro HTTP retorna o job para `pending` com backoff.
Após `PC24X7_TEAMS_MAX_ATTEMPTS`, o job vai para `quarantine` e exige diagnóstico; o worker
não repete indefinidamente e não transforma erro real em sucesso.

## Próximo incremento

Após o primeiro Adaptive Card real chegar ao Teams:

1. responder pelo `Action.Submit`;
2. confirmar o mesmo `conversation_id`;
3. retransmitir a mesma `activity.id` em teste controlado;
4. comprovar que não houve segunda chamada ao provedor;
5. conferir `correlation_id`, `content_sha256` e auditoria.
