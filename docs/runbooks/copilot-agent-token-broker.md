# Copilot Agent Token Broker

## Objetivo

Remover a dependência operacional de PAT de longa duração para GitHub Agent Tasks. O `Pending Development Orchestrator` continua aceitando `COPILOT_AGENT_TOKEN` como bootstrap/break-glass, mas prefere um token de usuário de curta duração obtido sob demanda por um broker autenticado via GitHub Actions OIDC.

## Fluxo alvo

1. O workflow solicita um JWT OIDC do GitHub Actions com audiência `reqsys-copilot-agent-token-broker`.
2. O entrypoint envia esse JWT ao broker por HTTPS, junto apenas de `repository` e `correlation_id`.
3. O broker valida assinatura, issuer, audience e claims de origem, restringindo ao repositório/workflow autorizados.
4. O broker obtém um GitHub App **user access token** válido para Agent Tasks e devolve somente o access token de curta duração.
5. O processo usa o token apenas em memória para `POST /agents/repos/{owner}/{repo}/tasks`.
6. Refresh token, client secret e demais credenciais do GitHub App permanecem exclusivamente no runtime/cofre do broker. Nada disso é persistido no repositório, artifact ou log do Actions.

## Configuração do workflow

Repository variables, não secretas:

- `COPILOT_AGENT_TOKEN_BROKER_URL`: endpoint HTTPS do broker.
- `COPILOT_AGENT_TOKEN_BROKER_AUDIENCE`: opcional; padrão `reqsys-copilot-agent-token-broker`.

O workflow possui `id-token: write`, necessário apenas para solicitar o JWT OIDC. Essa permissão não concede escrita em recursos do GitHub por si só.

## Contrato do broker

Requisição:

```http
POST /token
Authorization: Bearer <github-actions-oidc-jwt>
Content-Type: application/json

{"repository":"ericson-j-santos/reqsys-v2-enterprise-real","correlation_id":"<run-id>"}
```

Resposta de sucesso:

```json
{"access_token":"<short-lived-user-access-token>"}
```

O broker não deve devolver refresh token ao workflow.

## Política de confiança mínima

Validar no broker, no mínimo:

- `iss == https://token.actions.githubusercontent.com`;
- `aud == reqsys-copilot-agent-token-broker`;
- repositório exatamente `ericson-j-santos/reqsys-v2-enterprise-real`;
- `workflow_ref` exatamente do `pending-development-orchestrator.yml` na `main`;
- `ref == refs/heads/main`;
- evento restrito a `workflow_dispatch` ou `schedule`;
- token não expirado;
- GitHub App instalado somente nos repositórios necessários;
- permissões do App reduzidas ao mínimo necessário, incluindo `Agent tasks: read/write` para a rota Agent Tasks.

## Implementação de runtime

O serviço executável fica em `backend/token_broker/app.py` e possui imagem própria em `backend/token_broker/Dockerfile`.

Endpoints:

- `GET /healthz`: liveness; não prova autorização do GitHub App.
- `GET /readyz`: retorna `200` somente quando o runtime mínimo do broker está configurado; antes do bootstrap retorna `503`.
- `POST /token`: valida OIDC e retorna somente `access_token`; qualquer falha de configuração, OIDC ou rotação resulta em fail-closed.

O container deve executar com **uma réplica/um worker** enquanto o estado de rotação usar SQLite persistente. O Dockerfile fixa `--workers 1`. Para alta disponibilidade futura, substituir o estado local por armazenamento transacional compartilhado antes de aumentar réplicas.

O estado access/refresh é cifrado com Fernet antes de ser gravado em SQLite. A chave de cifra nunca deve residir no repositório. O volume persistente contém somente ciphertext e metadados de expiração.

### Segredos do broker

Provisionar no cofre/secret store do runtime, nunca no GitHub Actions:

- `BROKER_GITHUB_APP_CLIENT_ID`;
- `BROKER_GITHUB_APP_CLIENT_SECRET`;
- `BROKER_TOKEN_STATE_ENCRYPTION_KEY`;
- `BROKER_GITHUB_APP_REFRESH_TOKEN_BOOTSTRAP` somente para o primeiro seed após a autorização humana.

Configurações não secretas relevantes:

- `BROKER_TOKEN_STATE_DB_PATH` — usar volume persistente; o container assume `/var/lib/reqsys-token-broker/token-broker.db`;
- `BROKER_AUDIENCE` — padrão `reqsys-copilot-agent-token-broker`;
- `BROKER_ALLOWED_REPOSITORY` — padrão `ericson-j-santos/reqsys-v2-enterprise-real`;
- `BROKER_ALLOWED_WORKFLOW_REF` — workflow autorizado na `main`;
- `BROKER_ALLOWED_REF` — padrão `refs/heads/main`;
- `BROKER_ALLOWED_EVENTS` — padrão `workflow_dispatch,schedule`.

Após a primeira rotação bem-sucedida, remover `BROKER_GITHUB_APP_REFRESH_TOKEN_BOOTSTRAP` do runtime. O refresh token vigente permanece apenas no estado cifrado persistente. Se o volume for perdido, um bootstrap antigo já invalidado não deve ser tratado como recuperação automática; é necessário novo consentimento/autorização.

## Rotação

GitHub App user access tokens expiram por padrão em oito horas. O broker mantém o refresh token fora do GitHub Actions e substitui atomicamente o par access/refresh ao renovar. Enquanto o access token atual estiver fora da janela de renovação, o broker o reutiliza em memória/estado cifrado e não invalida o par desnecessariamente.

O workflow nunca grava ou atualiza repository secrets durante a rotação.

## Compatibilidade e fail-closed

Ordem de resolução no ReqSys:

1. `COPILOT_AGENT_TOKEN` existente — bootstrap/emergência;
2. broker OIDC configurado — estado alvo;
3. sem ambos — nenhuma credencial é fabricada; a rota Agent Tasks permanece indisponível e o orquestrador pode usar somente os fallbacks governados já existentes.

Falha de OIDC/broker não imprime corpo de erro potencialmente sensível e não faz fallback para shell, PAT embutido, arquivo `.env` ou credencial local.

## Bootstrap humano único

A criação/autorização inicial do GitHub App e o consentimento do usuário continuam sendo ações administrativas explícitas. Depois disso:

1. inserir `client_id`, `client_secret`, chave Fernet e refresh token inicial no secret store do broker;
2. iniciar o broker com volume persistente;
3. confirmar `/healthz=200` e `/readyz=200`;
4. configurar `COPILOT_AGENT_TOKEN_BROKER_URL=https://<host>/token` como variável não secreta do repositório;
5. executar o E2E positivo da issue #1677;
6. repetir a mesma entrada e comprovar que não foi criada segunda Agent Task;
7. remover `BROKER_GITHUB_APP_REFRESH_TOKEN_BOOTSTRAP` após a rotação inicial comprovada;
8. remover a dependência operacional de `COPILOT_AGENT_TOKEN` somente após o E2E positivo e a leitura independente do efeito.

O PAT manual permanece somente como contingência até esse critério ser atendido.

## Critério de conclusão

- testes unitários do provider e do broker verdes no SHA vigente;
- Pre-PR Readiness Gate verde no SHA vigente;
- broker real configurado e validando OIDC;
- `/healthz=200` e `/readyz=200` no runtime alvo;
- E2E positivo cria Agent Task branch-first sem PR automática;
- replay não cria segunda Agent Task;
- nenhum token/refresh token aparece em logs, artifacts ou comentários;
- `COPILOT_AGENT_TOKEN` manual removível sem regressão da rota.
