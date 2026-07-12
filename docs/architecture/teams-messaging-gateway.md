# Teams Messaging Gateway

## Decisao

O ReqSys passa a expor um gateway unico para mensageria Teams em `/v1/teams-gateway`.
O gateway centraliza roteamento, auditoria, fallback e mensagens de erro sobre as
limitacoes reais do Microsoft Graph.

## Rotas suportadas

| Canal | Uso recomendado | Usuario logado | Observacao |
|---|---|---:|---|
| `graph_delegado` | Chats humanos 1:1/grupo | Sim | Usa `usuario_access_token` MSAL com `ChatMessage.Send` e `Chat.ReadWrite`. Token expira em ~60-90 min, exige novo login. |
| `webhook` | Alertas automaticos, canal, eventos operacionais | Nao | Melhor caminho para automacao backend sem usuario logado. |
| `graph_app_only` | Cenarios onde app/bot e participante | Nao | Nao resolve chat humano-humano; usar apenas explicitamente. |
| `bot` | Chat humano 1:1 sem login por sessao | Nao | Azure Bot Service (Bot Framework). Implementado em codigo; infra real (Azure Bot resource) pendente — ver secao abaixo. |
| `flow_bot` | Chat humano 1:1 sem login por sessao, sem Azure Bot Service | Nao | Power Automate "Chat with Flow bot". Nao exige assinatura Azure; remetente aparece como "Workflows", nao com identidade propria do ReqSys. |

## Canal `bot` — implementacao e pendencias

Implementado em `backend/app/services/teams_gateway.py` (`_enviar_bot`, `_deve_usar_bot`,
`obter_conversa_referencia_bot`/`salvar_conversa_referencia_bot`) e no endpoint de
entrada `POST /v1/teams-gateway/bot/messages` (`backend/app/api/teams_gateway.py`),
que recebe as `Activity` do Bot Framework, valida o JWT assinado (issuer
`https://api.botframework.com`, biblioteca `PyJWT` + `PyJWKClient`) e persiste a
`conversationReference` (tabela `bot_conversa_referencia`) na primeira vez que o
bot e instalado/mencionado por um usuario — sem essa referencia previa, o Teams
nao permite iniciar uma conversa 1:1 do zero, entao o envio proativo retorna erro
claro (`motivo: conversa_bot_nao_instalada`) em vez de falhar silenciosamente.

Settings novas (`app/core/config.py`): `TEAMS_BOT_APP_ID`, `TEAMS_BOT_APP_TENANT_ID`,
`TEAMS_BOT_SECRET` — App Registration **dedicado**, separado do `AZURE_CLIENT_ID`
usado para login/Graph delegado. `GET /status` reflete `settings.teams_bot_configurado`
de verdade (nao mais um stub fixo).

**Pendente (fora de codigo, ver plano `magical-spinning-balloon` na sessao que criou
isso, 2026-07-07/08):**

1. O tenant `tieri659.onmicrosoft.com` tem Entra ID mas **nenhuma assinatura Azure
   vinculada** — o recurso Azure Bot (mesmo tier gratuito F0) exige uma assinatura.
   Bloqueado ate isso ser resolvido.
2. Depois de existir assinatura: criar o App Registration dedicado + Azure Bot
   resource (canal Teams habilitado), messaging endpoint apontando para
   `https://reqsys-api.fly.dev/v1/teams-gateway/bot/messages`.
3. Publicar `infra/teams-app/manifest.json` (+ `color.png`/`outline.png`, hoje
   placeholders gerados programaticamente — substituir pelo logo real antes de
   publicar) no catalogo do tenant e instalar no escopo pessoal do usuario-alvo,
   idealmente via Graph app-only (`AppCatalog.ReadWrite.All` +
   `TeamsAppInstallation.ReadWriteForUser.All`, ainda nao concedidas) para evitar
   que cada usuario precise adicionar o bot manualmente.
4. Antes de empacotar o manifest: substituir `id` (GUID valido, hoje
   `00000000-0000-0000-0000-000000000000`) e o placeholder `${{TEAMS_BOT_APP_ID}}`
   pelo App ID real do bot.

## Canal `flow_bot` — alternativa sem Azure Bot Service

Descoberto e implementado na mesma sessao do canal `bot` (2026-07-09), depois de
confirmar na documentacao oficial da Microsoft que a acao **"Post a message in a
chat or channel"** do conector Teams no Power Automate suporta a combinacao
`Post as: Flow bot`, `Post in: Chat with Flow bot` e um campo **Recipient**
dinamico — ou seja, um flow disparado por HTTP consegue entregar uma mensagem
real no chat 1:1 de qualquer usuario do tenant com o bot "Workflows" ja
existente, sem precisar registrar um Azure Bot, sem publicar Teams App e sem
assinatura Azure. Licenca M365 padrao e suficiente (nao exige conector premium).

### Ja existe um flow de producao pronto — reaproveite antes de criar um novo

Investigando o ambiente Dataverse do tenant (`pac solution list` + `pac
solution export`, 2026-07-09) foi encontrado um flow **ja em producao** que
faz exatamente isso: solution `robo_envia_mensagem_teams`, flow
`robo_envia_teams`, usando `Post as: Flow bot` / `Post in: Chat with Flow
bot` (operacao real `PostMessageToConversation` no conector `shared_teams`).
Ele e mais maduro que o design original desta doc: valida o payload
(`ParseJson`), tem tratamento de erro (`Scope_TRY`/`Scope_CATCH`) e registra
cada envio no SharePoint para auditoria.

**Antes de seguir o passo a passo abaixo, verifique se da pra simplesmente
reaproveitar esse flow existente como o primeiro `flow_bot_owner`** — copie a
URL do trigger dele no portal (My flows → `robo_envia_teams` → editar → card
do trigger → HTTP POST URL) e cadastre direto (passo 6). O schema de payload
do ReqSys (`_payload_flow_bot` em `teams_gateway.py`) ja foi ajustado pra
bater com o schema real desse flow (ver abaixo) especificamente para permitir
esse reaproveitamento.

**Atualizacao 2026-07-09 (mesmo dia) — ATENCAO, o flow candidato esta
desligado:** existem varias versoes/flows com nome parecido no ambiente
(`robo_envia_teams20260108v1`, `20260108v2`, `_v2.0.0`, `_v2.0.1` ×2,
`_v3.0.0`). Consultado via a nova funcao `listar_workflows_da_solution` (ver
"Automacao" abaixo): **so o `robo_envia_teams20260108v2`
(`workflowid=2c9d94b9-06ed-f011-8406-7ced8da92781`) esta de fato dentro da
solution `robo_envia_mensagem_teams`** — os outros sao flows soltos/versoes
paralelas. Verificado tambem que as versoes "mais novas" por nome
(`_v2.0.1` de fevereiro, `_v3.0.0`) **nao enviam mensagem no Teams** —
`_v2.0.1` (fev) perdeu o conector Teams no meio do caminho (so restou
SharePoint), e `_v3.0.0` e outra coisa (um template de login HTTP com URL/
credenciais de exemplo, sem nenhuma chamada de Teams/Graph). Nao sao
substitutas validas.

**Todos os 6 flows estao com `statecode=0` (Draft/Desligado)** — nenhum esta
rodando agora. Confirmado ao vivo (nao so pela API, o usuario tentou ligar
pelo portal): `robo_envia_teams20260108v2` nao liga porque a
`connectionReference` `new_sharedsharepointonline_fb142` (usada so pelo passo
de auditoria no SharePoint, nao pelo envio em si) nao esta compartilhada com
o usuario atual — erro exato do portal: *"A conexao ... nao pode ser usada
para ativar este fluxo... peca ao proprietario da conexao para ativar o
fluxo"*.

**Caminho recomendado (decisao do usuario, 2026-07-09): clonar so a parte de
Teams, sem a dependencia do SharePoint — manualmente, nao via API.** Motivo
de nao automatizar essa clonagem especifica via `ImportSolution`/criacao de
workflow: seria a primeira escrita ao vivo dessas APIs contra o tenant real,
sem teste previo, e o JSON de um cloud flow tem muitas dependencias internas
entre acoes (`runAfter`, `operationMetadataId`) — um erro na remocao
programada da acao `Criar_item__` (SharePoint) poderia corromper o flow de
forma dificil de depurar. Uma edicao manual no designer (remover 1 acao, ~2
min) e muito mais confiavel que uma primeira tentativa de escrita
automatizada. Passos: no flow `robo_envia_teams20260108v2` → **"..." → Save
As** (cria copia com conexoes proprias) → remover a acao `Criar_item__` →
reautorizar a conexao Teams quando solicitado (OAuth simples, self-service)
→ ligar o flow → copiar a URL do trigger → cadastrar via
`POST /v1/teams-gateway/flow-bot/owners`.

### Schema de payload — validado contra o flow real (nao inventado)

```json
{
  "to": "usuario@tieri659.onmicrosoft.com",
  "title": "Titulo da mensagem",
  "content": "Corpo da mensagem",
  "signature": "ReqSys",
  "correlationId": "uuid-do-gateway"
}
```

`to`, `title`, `content` e `signature` sao obrigatorios no flow existente
(`stampDate` e opcional, calculado automaticamente se ausente). `correlationId`
e opcional mas o ReqSys sempre envia o seu, o que da rastreabilidade de graca
no log de auditoria do SharePoint que o flow ja mantem.

### Passo a passo completo — padrao ouro (manual, uma vez por dono — só se for criar um flow NOVO)

**Pre-requisitos:** conta M365 com Power Automate incluido (licenca padrao,
sem premium), acesso a [make.powerautomate.com](https://make.powerautomate.com).

#### 1. Criar o flow

1. Entrar em make.powerautomate.com. Conferir o **Environment** selecionado no
   canto superior direito e anotar o nome — vai precisar dele se algum dia
   quiser automatizar via API (ver secao "Automacao" abaixo).
2. Menu lateral → **My flows** → **+ New flow** → **Automated cloud flow**.
3. Nome sugerido: `ReqSys Teams Gateway - Flow Bot - <nome do dono>` (ex.:
   `ReqSys Teams Gateway - Flow Bot - Ericson`).
4. No campo de busca de trigger, digitar **"When a Teams webhook request is
   received"** (conector Microsoft Teams), selecionar, **Create**.

#### 2. Configurar o schema do corpo esperado

1. Clicar no card do trigger.
2. Em **Request Body JSON Schema**, usar a opcao "generate from sample
   payload" e colar o schema real validado acima (`to`/`title`/`content`/
   `signature`/`correlationId`) — mantendo os mesmos nomes de campo do flow
   `robo_envia_teams` ja existente, para que qualquer `flow_bot_owner`
   (novo ou reaproveitado) responda ao mesmo contrato.

#### 3. Adicionar a acao de envio

1. **+ Novo passo** → buscar **"Post a message in a chat or channel"** →
   conector **Microsoft Teams**.
2. `Post as` = **Flow bot**.
3. `Post in` = **Chat with Flow bot**.
4. `Recipient` = conteudo dinamico → campo `to` (do trigger).
5. `Message` = conteudo dinamico → combine `title`/`content`/`signature` numa
   expressao, por exemplo:
   `concat('<b>', triggerBody()?['title'], '</b><br/>', triggerBody()?['content'], '<br/><i>— ', triggerBody()?['signature'], '</i>')`.

#### 4. Salvar, testar e capturar a URL

1. **Save**.
2. No card do trigger, abrir e copiar o **HTTP POST URL** gerado.
3. Testar de verdade via curl antes de cadastrar no ReqSys:

   ```bash
   curl -X POST "<URL copiada>" -H "Content-Type: application/json" \
     -d '{"to":"seu-email@tieri659.onmicrosoft.com","title":"Teste","content":"Teste ReqSys","signature":"ReqSys"}'
   ```

4. Confirmar no Teams: deve chegar uma mensagem do bot **"Workflows"** no seu
   chat pessoal com ele.

#### 5. Governanca (recomendado — facilita clonagem/manutencao depois)

1. No flow, **...** → **Details** → **Owners** → **+ Add owner**: adicionar
   pelo menos mais uma pessoa como co-dono, pra nao depender so de quem criou.
2. Mover o flow para dentro de uma **Solution** em vez de deixar solto em "My
   flows": menu **Solutions** → criar/abrir uma solution (ex.:
   `ReqSysTeamsGateway`) → **Add existing** → **Automation** → **Cloud flow** →
   selecionar o flow criado. Isso e o que habilita exportar/clonar de forma
   governada depois (ver secao "Automacao").

#### 6. Cadastrar no ReqSys

```bash
curl -X POST https://<host>/v1/teams-gateway/flow-bot/owners \
  -H "Authorization: Bearer <token admin>" \
  -H "Content-Type: application/json" \
  -d '{"owner_email":"ericson@tieri659.onmicrosoft.com","webhook_url":"<URL copiada>","prioridade":10}'
```

Implementado em `backend/app/services/teams_gateway.py` (`_deve_usar_flow_bot`,
`_enviar_flow_bot`, `_enviar_flow_bot_webhook`, `_payload_flow_bot`) — mesmo
padrao de retry/circuit breaker do canal `webhook`. `destino_id` no payload do
gateway passa a significar o e-mail/UPN do destinatario quando `modo=flow_bot`.
Em `auto`, o gateway prefere `bot` quando configurado (identidade propria,
suporta streaming) e cai para `flow_bot` só se `bot` nao estiver configurado —
ver `_deve_usar_flow_bot` em `teams_gateway.py`.

**Limitacoes conhecidas:** mensagem chega com o remetente "Workflows" (Flow
bot), nao com uma identidade de marca do ReqSys; cada flow fica vinculado a um
dono (o usuario que autenticou o conector Teams no Power Automate) — por isso
existe o mecanismo de redundancia abaixo.

## Redundancia: multiplos donos e failover automatico

Cada flow do Power Automate depende da conexao Teams de UM usuario especifico.
Quando esse usuario fica indisponivel por qualquer motivo (ferias, licenca,
desligamento, senha expirada, conta desativada), a Microsoft pode desligar o
flow — a doc oficial confirma isso: *"Workflows can become orphan flows in the
absence of an owner"*. Isso e um problema real de producao: uma unica pessoa
vira ponto unico de falha do canal de mensageria.

**Solucao adotada (2026-07-09):** em vez de tentar prever indisponibilidade
(status de Out-of-Office/calendario e um sinal fraco — pode estar errado ou
nao cobrir o motivo real da falha), o gateway cadastra **multiplos donos** e
faz **failover automatico quando a chamada falha de verdade** — o sinal mais
confiavel de que um flow foi desligado.

- Tabela `teams_flow_bot_owners` (`backend/app/models/teams_flow_bot_owner.py`):
  `owner_email`, `webhook_url`, `prioridade`, `ativo`, `observacao`.
- `_enviar_flow_bot` tenta os donos ativos em ordem de prioridade; cada um tem
  seu proprio circuit breaker (`_flow_bot_circuit_do_dono`), entao um dono
  quebrado nao afeta o circuito dos outros. So retorna falha se **todos**
  falharem, e a resposta lista as tentativas (`provider_response.tentativas`)
  para auditoria.
- `GET /v1/teams-gateway/status` reporta `donos_ativos` na rota `flow_bot`.
- CRUD administrativo (requer `require_admin`): `GET|POST /v1/teams-gateway/flow-bot/owners`,
  `PATCH|DELETE /v1/teams-gateway/flow-bot/owners/{id}` — editavel em runtime,
  sem redeploy. `webhook_url` nunca e devolvido nas respostas (so um booleano
  `webhook_configurado`), pois a URL do trigger costuma embutir uma assinatura.
- Se nenhum dono ativo existir no banco, cai para `TEAMS_FLOW_BOT_WEBHOOK_URL`
  do `.env` como um unico alvo (compatibilidade com o setup simples).

### Automacao: o que da e o que nunca vai dar

**O unico passo que nunca vai dar pra automatizar, em nenhuma das opcoes
abaixo:** a conexao Teams de cada novo dono. Confirmado por 3 fontes
independentes durante a pesquisa desta sessao — conectores como Teams,
SharePoint e Outlook no Power Automate exigem OAuth delegado interativo por
design, sem suporte a client credentials/service principal; mesmo a Opcao B
(Solutions) so consegue *vincular* uma conexao que ja existe, nunca *criar*
uma do zero. E ~1-2 minutos de clique de consentimento, uma vez por dono, sem
alternativa via API — limitacao da Microsoft, nao do ReqSys.

**Fora isso, existem DUAS ferramentas, para DOIS problemas diferentes** (as
duas implementadas em `backend/app/services/teams_flow_bot_provisioning.py`):

**Opcao A — clonar donos de backup no MESMO ambiente.** Use quando: voce quer
N flows irmaos (um por dono de backup) coexistindo no mesmo ambiente, pra
redundancia (ver secao anterior). `capturar_definicao_flow` busca a definicao
real de um flow existente via `GET` em `api.flow.microsoft.com`,
`clonar_definicao_para_novo_dono` troca so a `connectionReference` e gera um
GUID novo, `criar_flow_a_partir_definicao` recria via `PUT`. Tudo isso
orquestrado por `clonar_flow_para_novo_dono`, exposto em
`POST /v1/teams-gateway/flow-bot/clonar-flow` (`require_admin`; parametros:
`environment`, `flow_id_origem`, `nova_connection_id`, `novo_display_name`).
Usa uma API que a Microsoft nao documenta publicamente como estavel para
terceiros (a mesma que o proprio portal usa internamente) — risco de quebrar
sem aviso numa mudanca de produto, mas e o unico mecanismo que realmente cria
copias paralelas independentes no mesmo ambiente.

**Opcao B — promover o flow_bot entre ambientes (dev → test → prod).** Use
quando: voce quer o MESMO flow existindo em ambientes diferentes, cada um com
o dono/conexao daquele ambiente — nao serve para multiplicar donos dentro do
mesmo ambiente (Solutions casam componentes por "unique name": reimportar a
mesma solution no mesmo ambiente atualiza o flow existente, nao cria um irmao
novo — descoberta importante desta sessao que descartou a ideia inicial de
usar Solutions no lugar da Opcao A). Usa so APIs Dataverse 100% documentadas:

1. `exportar_solution` — Dataverse `ExportSolution` action, retorna o `.zip`
   em base64 (mesmo formato do export manual pelo portal).
2. `importar_solution` — Dataverse `ImportSolution` (mesmo padrao ja usado em
   `copilot_studio_provisioner.py::_importar_solution_dataverse` para o
   Copilot Studio, reaproveitado aqui como convencao de auth/headers).
3. `vincular_connection_reference` — apos o import, a `connectionReference`
   chega **sem vinculo** (Microsoft confirma oficialmente: *"connection
   references arrive unbound"*). Resolvido com `PATCH` direto na tabela
   Dataverse `connectionreferences`, setando `connectionid` — CRUD padrao,
   nao e reverse-engineering.
4. `ativar_flow` — `PATCH` na tabela `workflows` (`statecode=1`,
   `statuscode=2`, convencao Dataverse para "Activated"; valores nao validados
   ao vivo ainda neste ambiente).

Tudo orquestrado por `promover_flow_para_ambiente`, exposto em
`POST /v1/teams-gateway/flow-bot/promover-solution` (`require_admin`;
parametros: `environment_url_origem`, `environment_url_destino`,
`solution_name`, `connection_reference_logical_name`,
`connection_id_destino`, `novo_flow_display_name`).

**Atualizacao 2026-07-09 (mesmo dia, mais tarde) — Opcao B validada ao vivo:**
o gap de permissao acima foi resolvido. `ericsonjosedossantos@tieri659.onmicrosoft.com`
tem Global Admin/Power Platform Admin de verdade — login interativo via
`pac auth create`, depois `pac admin application register --application-id <AZURE_CLIENT_ID>`
e `pac admin assign-user --environment https://orga258f260.crm2.dynamics.com
--user <AZURE_CLIENT_ID> --role "System Customizer" --application-user`, ambos
com sucesso. Confirmado ao vivo logo em seguida: `obter_workflow_id_por_nome`
e `obter_connection_reference_id` (Opcao B) retornaram GUIDs reais do flow
`robo_envia_teams` (`workflowid=2c9d94b9-06ed-f011-8406-7ced8da92781`,
`connectionreferenceid=4c3420f9-5167-f011-b4cb-000d3a889c3f`) — leitura
Dataverse via `AZURE_CLIENT_ID` funciona de verdade agora. `ImportSolution`/
`PATCH` (escrita) ainda nao foram testados contra o flow de producao real, de
proposito, para nao arriscar desativa-lo sem necessidade.

**Opcao A (Flow Management API bruta) continua bloqueada — mas por um motivo
diferente e mais especifico:** `capturar_definicao_flow` retornou `403` mesmo
com a nova permissao Dataverse. Motivo: a Flow Management API
(`api.flow.microsoft.com`) usa um modelo de autorizacao proprio, por
co-propriedade do flow especifico (a mesma logica de "Owners" que aparece no
designer do Power Automate) — nao e coberto pelo papel `System Customizer` do
Dataverse. Para a Opcao A funcionar num flow existente, o app precisaria ser
adicionado como co-dono desse flow especificamente (via portal, "..." →
Details → Owners → + Add owner, usando o Object ID do service principal
`AZURE_CLIENT_ID` como se fosse um usuario) — nao testado ainda.

Testes automatizados continuam com `httpx` mockado
(`backend/tests/test_teams_flow_bot_provisioning.py` para a Opcao A,
`backend/tests/test_teams_flow_bot_solution_provisioning.py` para a Opcao B)
ate essa permissao ser concedida.

## Contrato principal

`POST /v1/teams-gateway/messages`

```json
{
  "destino_tipo": "chat",
  "modo": "auto",
  "destino_id": "chat-id",
  "texto": "Mensagem ReqSys",
  "usuario_access_token": "token-delegado-opcional",
  "permitir_fallback": true,
  "metadata": {
    "titulo": "ReqSys"
  }
}
```

Resposta padronizada:

```json
{
  "entregue": true,
  "canal_usado": "graph_delegado",
  "destino_tipo": "chat",
  "correlation_id": "uuid",
  "fallback_usado": false,
  "message_id": "msg-id"
}
```

## Politica padrao ouro

- Chat humano sem `usuario_access_token` nao tenta burlar o Graph; retorna erro claro.
- Automacao backend deve preferir `webhook` ou, no futuro, `bot`.
- `auto` usa Graph delegado quando ha token, webhook quando o destino e operacional,
  e bloqueia quando nao ha rota segura.
- Toda tentativa registra `teams_gateway` no historico de integracoes.
- Webhook tem retry e circuit breaker proprio.
- Endpoints antigos de `hub_lowcode` continuam compativeis.

## Endpoints

- `GET /v1/teams-gateway/status`
- `POST /v1/teams-gateway/routes`
- `POST /v1/teams-gateway/messages`
- `POST /v1/teams-gateway/messages/delegated`
- `POST /v1/teams-gateway/messages/webhook`
- `POST /v1/teams-gateway/bot/messages` — webhook de entrada do Bot Framework (canal `bot`).
- `GET|POST /v1/teams-gateway/flow-bot/owners`, `PATCH|DELETE /v1/teams-gateway/flow-bot/owners/{id}` — CRUD de donos/backups do canal `flow_bot` (`require_admin`).
- `POST /v1/teams-gateway/flow-bot/clonar-flow` — clona a definicao de um flow existente para um novo dono no mesmo ambiente (`require_admin`, Opcao A da secao "Automacao").
- `POST /v1/teams-gateway/flow-bot/promover-solution` — promove o flow_bot entre ambientes via Power Platform Solutions (`require_admin`, Opcao B da secao "Automacao").
- `GET /v1/teams-gateway/flow-bot/flows?environment=...&nome_contem=...` — lista cloud flows cujo nome contem o texto informado, com status/data de modificacao — resolve ambiguidade entre flows/versoes parecidos sem precisar adivinhar no portal (`require_admin`).
- `GET /v1/teams-gateway/flow-bot/solutions/{solution_name}/flows?environment=...` — lista os flows que estao DE FATO dentro de uma Solution especifica, via `solutioncomponents` (`require_admin`).
