# Copilot Agent Token Broker

## Objetivo

Remover a dependência operacional de PAT de longa duração para GitHub Agent Tasks. O `Pending Development Orchestrator` continua aceitando `COPILOT_AGENT_TOKEN` como bootstrap/break-glass, mas prefere um token de usuário de curta duração obtido sob demanda por um broker autenticado via GitHub Actions OIDC.

## Fluxo alvo

1. O workflow solicita um JWT OIDC do GitHub Actions com audiência `reqsys-copilot-agent-token-broker`.
2. O entrypoint envia esse JWT ao broker por HTTPS, junto apenas de `repository` e `correlation_id`.
3. O broker valida assinatura, issuer, audience e claims de origem, restringindo ao repositório/workflow autorizados.
4. O broker obtém um GitHub App **user access token** válido para Agent Tasks e devolve somente o access token de curta duração.
5. O processo usa o token apenas em memória para `POST /agents/repos/{owner}/{repo}/tasks`.
6. Refresh token, client secret e demais credenciais do GitHub App permanecem exclusivamente no cofre do broker. Nada disso é persistido no repositório, artifact ou log do Actions.

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
- workflow/ref/evento permitidos;
- token não expirado;
- GitHub App instalado somente nos repositórios necessários;
- permissões do App reduzidas ao mínimo necessário, incluindo `Agent tasks: read/write` para a rota Agent Tasks.

## Rotação

GitHub App user access tokens expiram por padrão em oito horas. O broker deve manter o refresh token fora do GitHub Actions e substituir atomicamente o par access/refresh ao renovar. O workflow nunca grava ou atualiza repository secrets durante a rotação.

## Compatibilidade e fail-closed

Ordem de resolução:

1. `COPILOT_AGENT_TOKEN` existente — bootstrap/emergência;
2. broker OIDC configurado — estado alvo;
3. sem ambos — nenhuma credencial é fabricada; a rota Agent Tasks permanece indisponível e o orquestrador pode usar somente os fallbacks governados já existentes.

Falha de OIDC/broker não imprime corpo de erro potencialmente sensível e não faz fallback para shell, PAT embutido, arquivo `.env` ou credencial local.

## Bootstrap humano único

A criação/autorização inicial do GitHub App e o consentimento do usuário continuam sendo ações administrativas explícitas. Depois disso, o broker assume emissão e renovação automática dos tokens de curta duração. O PAT manual permanece somente como contingência e pode ser removido após o E2E positivo do broker.

## Critério de conclusão

- testes unitários do provider verdes;
- Pre-PR Readiness Gate verde no SHA vigente;
- broker real configurado e validando OIDC;
- E2E positivo cria Agent Task branch-first sem PR automática;
- replay não cria segunda Agent Task;
- nenhum token/refresh token aparece em logs, artifacts ou comentários;
- `COPILOT_AGENT_TOKEN` manual removível sem regressão da rota.
