# Teams → GitHub Actions governado

## Objetivo

Permitir que uma mensagem recebida no Microsoft Teams execute verificações do ReqSys sem exigir que o usuário navegue até o GitHub.

A primeira versão aceita apenas operações não destrutivas:

- `essential`: executa o conjunto essencial já mantido por `.github/workflows/actions-dispatcher.yml`;
- `all`: executa o conjunto completo já mantido pelo mesmo dispatcher.

Merge, aprovação de PR, deploy, exclusão e alteração de segredo não fazem parte deste contrato.

## Fluxo

```text
GitHub / ReqSys
    ↓
Power Automate recebe o evento
    ↓
Post adaptive card and wait for a response
    ↓
Usuário escolhe uma ação no Teams
    ↓ Action.Submit
Power Automate valida reqsys_action/mode/ref
    ↓ X-Service-Token
POST /v1/teams-gateway/github-actions/dispatch
    ↓
ReqSys valida feature flag + token + repo + workflow + mode + ref
    ↓
GitHub REST workflow dispatch
    ↓
.github/workflows/actions-dispatcher.yml
    ↓
ci.yml / governance-quality-gates.yml / governanca-padrao-ouro.yml / ...
```

## Endpoints

### `GET /v1/teams-gateway/github-actions/status`

Retorna somente metadados seguros da integração. Não retorna o `GITHUB_PAT`.

Autenticação: JWT admin ou `X-Service-Token` com escopo `teams_gateway:github_actions`.

### `POST /v1/teams-gateway/github-actions/card`

Gera o Adaptive Card com botões `Action.Submit` para o Flow bot atual.

Exemplo de entrada:

```json
{
  "titulo": "ReqSys — falha no CI",
  "descricao": "Escolha a validação que deseja executar.",
  "ref": "main",
  "github_url": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions"
}
```

Os botões retornam somente:

```json
{
  "reqsys_action": "github_actions_dispatch",
  "mode": "essential",
  "ref": "main",
  "correlation_id": "..."
}
```

Nenhum token, repositório ou nome de workflow é enviado ao cliente Teams.

### `POST /v1/teams-gateway/github-actions/dispatch`

Exemplo:

```json
{
  "mode": "essential",
  "ref": "main"
}
```

Autenticação: JWT admin ou `X-Service-Token` com escopo `teams_gateway:github_actions`.

## Configuração

```dotenv
TEAMS_GITHUB_ACTIONS_ENABLED=false
TEAMS_GITHUB_ACTIONS_REPO=ericson-j-santos/reqsys-v2-enterprise-real
TEAMS_GITHUB_ACTIONS_WORKFLOW=actions-dispatcher.yml
TEAMS_GITHUB_ACTIONS_DISPATCH_REF=main
GITHUB_PAT=
```

Recomendação para o token GitHub: usar token de granularidade fina limitado ao repositório do ReqSys, com permissão de escrita em Actions. Não colocar o token no Adaptive Card nem no Power Automate; o token permanece no cofre/configuração do backend.

## Alteração necessária no Power Automate

O fluxo atual de notificação usa o Flow bot. Para que `Action.Submit` funcione, a etapa que publica o cartão deve ser uma variante **Post adaptive card and wait for a response**. Cartões publicados sem espera aceitam somente ações de URL de forma confiável.

Após a resposta:

1. Validar `reqsys_action == github_actions_dispatch`.
2. Permitir somente `mode` igual a `essential` ou `all`.
3. Reaproveitar `ref` recebido no cartão; não aceitar repositório/workflow enviados pelo usuário.
4. Chamar `POST /v1/teams-gateway/github-actions/dispatch` com `X-Service-Token` escopado.
5. Atualizar o cartão com o resultado e `correlation_id`.
6. Se o backend retornar erro, exibir mensagem objetiva e manter o link de fallback para o GitHub.

## Segurança

- feature flag desligada por padrão;
- allowlist de modos;
- validação estrita de `ref`;
- repositório e workflow definidos somente no servidor;
- autenticação service-to-service escopada;
- `GITHUB_PAT` nunca é retornado ao Teams;
- auditoria de solicitação, sucesso e falha com `correlation_id` e ator;
- respostas de erro do GitHub são sanitizadas antes de chegar ao cliente.

## Critério de conclusão ponta a ponta

A funcionalidade só pode ser marcada como concluída quando houver evidência de todos os itens abaixo:

1. PR do backend aprovado e CI verde.
2. Configuração DEV com `TEAMS_GITHUB_ACTIONS_ENABLED=true` e credencial GitHub válida.
3. Power Automate alterado para publicar cartão e aguardar resposta.
4. Clique em **Executar verificações essenciais** no Teams.
5. Resposta HTTP 2xx do ReqSys com `correlation_id`.
6. Nova execução do `Actions Dispatcher — ReqSys` criada no GitHub para a mesma `ref`.
7. Cartão do Teams atualizado com confirmação ou erro sanitizado.
8. Segundo clique/novo cartão validado para o modo `all` sem expor credenciais.

## Próximo incremento

Depois da validação do fluxo atual via Power Automate, o Bot Framework nativo pode receber `Action.Execute` diretamente em `/v1/teams-gateway/bot/messages`. Essa evolução elimina a espera mantida pelo Flow e permite atualizar o próprio cartão com o resultado, mas deve ser implementada separadamente para preservar o funcionamento atual.
