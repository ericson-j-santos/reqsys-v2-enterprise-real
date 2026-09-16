# GitHub App Manifest Bootstrap

## Objetivo

Reduzir o bootstrap administrativo do broker de Agent Tasks a uma única sequência de consentimento no GitHub, sem copiar `client_secret`, refresh token, PEM ou webhook secret para o chat, GitHub Actions, repositório ou logs.

Fluxo alvo:

`GET /bootstrap/github-app` → `Create GitHub App` → instalação/autorização → callback → estado cifrado → `/readyz=200` → E2E governado da issue #1677.

A criação da GitHub App e o consentimento do usuário continuam sendo ações humanas explícitas. O broker automatiza tudo antes e depois dessa fronteira.

## Pré-requisitos de runtime

O bootstrap permanece desabilitado por padrão. Para habilitá-lo no runtime do broker:

- `BROKER_BOOTSTRAP_ENABLED=true`;
- `BROKER_PUBLIC_BASE_URL=https://<host-publico-do-broker>`;
- `BROKER_TOKEN_STATE_ENCRYPTION_KEY=<chave-fernet-no-secret-store>`;
- volume persistente em `BROKER_TOKEN_STATE_DB_PATH`.

A chave Fernet é a única raiz secreta pré-existente necessária ao serviço. Ela deve ser provisionada pelo secret store do runtime e nunca deve ser enviada ao chat ou versionada.

Configurações opcionais:

- `BROKER_GITHUB_APP_NAME` — padrão `ReqSys Copilot Agent Token Broker`;
- `BROKER_BOOTSTRAP_STATE_TTL_SECONDS` — padrão `900`;
- `BROKER_GITHUB_APP_MANIFEST_PERMISSION` — padrão `agent_tasks`.

`Agent tasks` está em public preview no GitHub. O endpoint de criação de Agent Tasks exige GitHub App **user access token** e permissão de repositório `Agent tasks: read/write`; installation access token não é aceito. O parâmetro do Manifest deve continuar sendo revalidado no GitHub enquanto a API permanecer em preview. Qualquer rejeição do Manifest encerra o bootstrap em fail-closed.

## Fluxo executável

1. O operador abre `https://<host>/bootstrap/github-app`.
2. O broker gera um `state` criptograficamente aleatório, persiste somente SHA-256 + finalidade + expiração e apresenta o formulário para `https://github.com/settings/apps/new`.
3. O Manifest solicita somente a permissão de Agent Tasks em `write`, não assina eventos e usa `request_oauth_on_install=true`.
4. O usuário confirma `Create GitHub App` no GitHub.
5. O GitHub retorna um `code` temporário ao callback de Manifest.
6. O broker consome o `state` exatamente uma vez, converte o `code` e persiste cifrados somente `app_id`, `slug`, `client_id` e `client_secret`.
7. PEM e webhook secret retornados pelo GitHub são deliberadamente descartados porque não são necessários para o fluxo user-to-server do broker.
8. O broker cria um segundo `state` one-time e redireciona para a instalação da App.
9. O usuário instala/autoriza a App no GitHub.
10. O callback OAuth troca o `code` por access/refresh token e persiste ambos cifrados no mesmo volume.
11. O runtime é recarregado em memória e `/readyz` passa a refletir o novo estado sem reinício do processo.
12. A partir daí, o workflow autorizado pode usar OIDC para chamar `POST /token`.

## Controles contra falso positivo e replay

- bootstrap desligado por padrão;
- URL pública deve ser HTTPS;
- `state` separado para Manifest e OAuth;
- `state` armazenado apenas como SHA-256;
- TTL limitado e consumo atômico uma única vez;
- callback com `state` ausente, incorreto, expirado ou reutilizado é rejeitado antes de chamada externa;
- credenciais e tokens são cifrados com Fernet antes da persistência;
- respostas HTML não exibem segredos;
- PEM e webhook secret não são persistidos;
- `/healthz=200` não equivale a autorização;
- `/readyz=200` somente após credenciais da App e refresh token autorizado existirem;
- o E2E real continua obrigatório antes de retirar o PAT de contingência.

## Validação pós-autorização

A autorização humana não encerra o TODO. A automação deve então:

1. confirmar `/healthz=200`;
2. confirmar `/readyz=200`;
3. configurar `COPILOT_AGENT_TOKEN_BROKER_URL=https://<host>/token` pela rota administrativa aprovada;
4. executar o E2E positivo da issue #1677 no SHA e ambiente vigentes;
5. localizar a Agent Task por leitura independente;
6. repetir a mesma entrada/correlation key;
7. provar que o replay não criou segunda Agent Task;
8. comprovar que logs/artifacts/comentários não contêm tokens;
9. só então remover a dependência operacional de `COPILOT_AGENT_TOKEN`.

Até a conclusão dessas verificações, o estado correto é `parcialmente validado` ou `bloqueado por autorização/runtime`, nunca `concluído`.
