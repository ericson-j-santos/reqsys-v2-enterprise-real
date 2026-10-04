# GitHub App Manifest Bootstrap

## Objetivo

Reduzir o bootstrap administrativo do broker de Agent Tasks a uma sequência guiada de consentimento no GitHub, sem copiar `client_secret`, refresh token, PEM ou webhook secret para o chat, GitHub Actions, repositório ou logs.

Fluxo alvo:

`GET /bootstrap/github-app` → `Create GitHub App` → `Install` → OAuth com `state` explícito → callback → validação de acesso ao ReqSys → estado cifrado → `/readyz=200` → E2E governado da issue #1677.

A criação da GitHub App, a instalação e o consentimento do usuário continuam sendo ações humanas explícitas no GitHub. O broker automatiza tudo antes, entre e depois dessas fronteiras.

## Pré-requisitos de runtime

O bootstrap permanece desabilitado por padrão. Para habilitá-lo no runtime do broker:

- `BROKER_BOOTSTRAP_ENABLED=true`;
- `BROKER_PUBLIC_BASE_URL=https://<host-publico-do-broker>`;
- chave Fernet mantida fora do repositório e injetada pelo secret store/arquivo protegido do host;
- volume persistente em `BROKER_TOKEN_STATE_DB_PATH`.

A chave Fernet é a única raiz secreta pré-existente necessária ao serviço. Ela nunca deve ser enviada ao chat, versionada ou escrita em logs.

Configurações opcionais:

- `BROKER_GITHUB_APP_NAME` — padrão `ReqSys Copilot Agent Token Broker`;
- `BROKER_BOOTSTRAP_STATE_TTL_SECONDS` — padrão `900`;
- `BROKER_GITHUB_APP_MANIFEST_PERMISSION` — padrão `agent_tasks`.

`Agent tasks` está em public preview no GitHub. O endpoint de criação de Agent Tasks exige GitHub App **user access token** e permissão de repositório `Agent tasks: read/write`; installation access token não é aceito. O parâmetro do Manifest deve continuar sendo revalidado no GitHub enquanto a API permanecer em preview. Qualquer rejeição do Manifest encerra o bootstrap em fail-closed.

## Runtime canônico: PC24x7

Para este broker, o runtime primário é o **PC24x7** já existente. Não criar um novo runtime pago enquanto o PC24x7 estiver disponível e atender persistência, HTTPS, restart e isolamento de segredos.

O serviço é definido em `docker-compose.pc24x7-token-broker.yml` e usa:

- `backend/token_broker/Dockerfile`;
- `restart: unless-stopped`;
- uma única instância/worker enquanto o estado permanecer em SQLite;
- volume `reqsys-token-broker-state` montado em `/var/lib/reqsys-token-broker`;
- bind local em `127.0.0.1:${BROKER_HOST_PORT:-18080}`;
- arquivo de segredo externo ao repositório indicado por `BROKER_TOKEN_STATE_ENCRYPTION_KEY_FILE`;
- `BROKER_PUBLIC_BASE_URL` obrigatório, apontando para uma URL HTTPS estável.

Subida governada do serviço:

```bash
docker compose -f docker-compose.pc24x7-token-broker.yml up -d --build
```

Antes da subida, o host deve fornecer somente referências/configurações, nunca valores secretos no Git:

```bash
export BROKER_TOKEN_STATE_ENCRYPTION_KEY_FILE=/caminho/protegido/fernet.key
export BROKER_PUBLIC_BASE_URL=https://<hostname-estavel>
```

O arquivo da chave deve existir apenas no host autorizado, com permissões restritas. O Compose monta esse arquivo em `/run/secrets/broker_token_state_encryption_key`; o processo lê a chave em memória ao iniciar e não a imprime.

### Exposição HTTPS

O Quick Tunnel (`*.trycloudflare.com`) pode ser usado somente para diagnóstico transitório. Ele **não** é endpoint final deste broker porque a URL muda após reinício e quebraria callbacks/configuração de `COPILOT_AGENT_TOKEN_BROKER_URL`.

A rota operacional preferida é um **Cloudflare Tunnel nomeado com hostname estável** apontando para `http://127.0.0.1:${BROKER_HOST_PORT:-18080}`. Se já existir uma zona/hostname estável do PC24x7, deve ser reutilizada antes de contratar infraestrutura adicional.

Render permanece apenas como contingência: só deve ser considerado quando houver indisponibilidade comprovada ou incapacidade técnica do PC24x7 para cumprir os requisitos acima, com causa registrada e decisão explícita.

## Fluxo executável

1. O operador abre `https://<host>/bootstrap/github-app`.
2. O broker gera um `state` criptograficamente aleatório, persiste somente SHA-256 + finalidade + expiração e apresenta o formulário para `https://github.com/settings/apps/new`.
3. O Manifest solicita somente a permissão de Agent Tasks em `write`, não assina eventos, configura um `setup_url` do broker e mantém `request_oauth_on_install=false`.
4. O usuário confirma `Create GitHub App` no GitHub.
5. O GitHub retorna um `code` temporário ao callback de Manifest junto com o `state` original.
6. O broker consome o `state` exatamente uma vez, converte o `code` e persiste cifrados somente `app_id`, `slug`, `client_id` e `client_secret`.
7. PEM e webhook secret retornados pelo GitHub são deliberadamente descartados porque não são necessários para o fluxo user-to-server do broker.
8. Antes de redirecionar para a instalação, o broker cria um `state` one-time para a etapa de instalação e o envia apenas em cookie `Secure`, `HttpOnly`, `SameSite=Lax`, restrito ao callback de instalação.
9. O usuário instala a App no GitHub. O GitHub retorna ao `setup_url` com `installation_id`; esse identificador não é confiado isoladamente.
10. O broker exige o cookie one-time da etapa de instalação, consome-o e cria um novo `state` OAuth associado ao `installation_id`.
11. O broker redireciona explicitamente para `https://github.com/login/oauth/authorize` com `client_id`, `redirect_uri` exato e `state`; assim o CSRF/replay permanece controlado pelo broker em vez de depender da transição automática `request_oauth_on_install`.
12. Após o consentimento, o callback OAuth consome o `state`, troca o `code` por access/refresh token e usa o access token para consultar a instalação indicada.
13. O bootstrap só aceita a autorização se `GET /user/installations/{installation_id}/repositories` comprovar que a instalação alcança `ericson-j-santos/reqsys-v2-enterprise-real`.
14. Só depois dessa leitura independente o broker persiste access/refresh token cifrados, recarrega o runtime em memória e permite `/readyz=200` sem reinício.
15. A partir daí, o workflow autorizado pode usar OIDC para chamar `POST /token`.

## Controles contra falso positivo e replay

- bootstrap desligado por padrão;
- URL pública deve ser HTTPS e estável para operação normal;
- estados separados para Manifest, instalação e OAuth;
- estados armazenados apenas como SHA-256;
- TTL limitado e consumo atômico uma única vez;
- cookie de instalação `Secure`, `HttpOnly`, `SameSite=Lax` e path-restricted;
- callback com estado ausente, incorreto, expirado ou reutilizado é rejeitado antes de prosseguir;
- `installation_id` não é usado como prova por si só;
- a instalação precisa provar acesso real ao repositório ReqSys via API autenticada pelo user access token;
- credenciais e tokens são cifrados com Fernet antes da persistência;
- respostas HTML não exibem segredos;
- PEM e webhook secret não são persistidos;
- `/healthz=200` não equivale a autorização;
- `/readyz=200` somente após credenciais da App, refresh token autorizado e prova de acesso da instalação ao ReqSys existirem;
- restart do container/host deve preservar o SQLite e manter a capacidade de leitura cifrada do estado;
- o E2E real continua obrigatório antes de retirar o PAT de contingência.

## Validação pós-autorização

A autorização humana não encerra o TODO. A automação deve então:

1. confirmar `/healthz=200`;
2. confirmar `/readyz=200`;
3. reiniciar o container e confirmar novamente `/healthz=200` e `/readyz=200`, provando persistência;
4. configurar `COPILOT_AGENT_TOKEN_BROKER_URL=https://<host>/token` pela rota administrativa aprovada;
5. executar o E2E positivo da issue #1677 no SHA e ambiente vigentes;
6. localizar a Agent Task por leitura independente;
7. repetir a mesma entrada/correlation key;
8. provar que o replay não criou segunda Agent Task;
9. comprovar que logs/artifacts/comentários não contêm tokens;
10. só então remover a dependência operacional de `COPILOT_AGENT_TOKEN`.

Até a conclusão dessas verificações, o estado correto é `parcialmente validado` ou `bloqueado por autorização/runtime`, nunca `concluído`.
