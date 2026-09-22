# Runbook — ações humanas Power Platform (blueprint DEV → TEST → PROD)

Este runbook responde a uma pergunta específica: **do blueprint de ações humanas, o que dá
para automatizar dentro do repositório e o que continua inevitavelmente manual?**

O corte é honesto. Autenticação interativa (OAuth), criação de token no GitHub e decisão de
qual ambiente Power Platform será TEST/PROD não são automatizáveis por um agente — nenhuma
API do repositório substitui um humano logado. O que **é** automatizável é tudo em volta:
registrar a decisão de forma auditável, validar formato, bloquear promoção incoerente,
encerrar a issue quando a evidência chegar e limpar o ambiente local com segurança.

## Mapa das 7 ações

| # | Ação | Automatizável? | O que passou a existir |
|---|---|---|---|
| 1 | Renovar `GH_PAT_ACTIONS` | ⛔ Gerar/colar o token — parcial no aceite | Watcher horário já validava a credencial mas **só comentava** na #1130; agora **encerra a issue** (`github-workflow-permission-readiness-watch.yml`) |
| 2 | Remover 11 worktrees órfãos | ✅ Totalmente | `scripts/limpar-worktrees-orfaos.ps1` — idempotente, sem `--force`, com evidência JSON |
| 3 | Definir ambientes TEST/PROD | ⛔ A escolha — ✅ o registro | `config/power-platform/environments.json` + validador + gate de CI |
| 4 | Autorizar conexão Teams | ⛔ OAuth interativo | Os 3 valores exigidos viram campos validados no registro (GUID, nome lógico) |
| 5 | Primeira promoção DEV → TEST | ⛔ O disparo — ✅ a guarda | `teams-flow-bot-promotion.yml` agora confere os inputs contra o registro antes de promover |
| 6 | Segundo proprietário do flow | ⛔ Power Automate UI | Nada a automatizar; passo a passo permanece no blueprint |
| 7 | Assinatura Azure (tenant `tieri659`) | ⚪ Adiado | Só relevante se `flow_bot` migrar para Azure Bot Service |

## 1. `GH_PAT_ACTIONS` — o que mudou no aceite

O critério de conclusão da issue #1130 diz: *"watcher publica evidência e encerra esta
issue"*. O watcher publicava a evidência e comentava, mas **não encerrava** — o aceite ficava
manual para sempre. O passo `Record first validated credential readiness` agora:

1. comenta uma única vez (marcador `<!-- reqsys-gh-workflow-token-ready -->`);
2. lê o estado atual da issue;
3. encerra com `state_reason: completed` se ainda estiver aberta.

Nenhum valor de segredo é lido, impresso ou alterado. A parte humana continua sendo gerar o
token fine-grained (Contents/Issues/Workflows → *Read and write*, escopo apenas
`reqsys-v2-enterprise-real`) e colá-lo em **Settings → Secrets and variables → Actions**.

Depois de salvar o segredo, não espere a próxima hora cheia:

```
Actions → GitHub Workflow Permission Readiness Watch → Run workflow → enforce: true
```

Verde nesse run = autenticação, criação/escrita/remoção da branch efêmera e permissão de
workflow validadas, evidência publicada e #1130 encerrada. Segredo salvo, sozinho, não conta.

## 2. Worktrees órfãos — automatizado

```powershell
cd github-main
.\scripts\limpar-worktrees-orfaos.ps1 -Simular   # relatório, sem remover nada
.\scripts\limpar-worktrees-orfaos.ps1            # execução real
```

O script cobre os 11 worktrees do blueprint por padrão e é seguro por construção:

- **nunca** usa `git worktree remove --force`;
- recusa remover um worktree com arquivos não commitados **ou** com commits ausentes do
  upstream (ou de `origin/main`, quando não há upstream), dizendo exatamente o que segurou;
- trata worktree já removido como sucesso (idempotente);
- roda `git worktree prune` e reconfere a lista ao final;
- não executa `checkout`, `reset` ou `stash` — respeita o guardrail do `CLAUDE.md`;
- grava `artifacts/governance/worktree-cleanup.json` com `force_utilizado: false` e
  `branches_removidos: false`.

Sai com código 1 enquanto sobrar algum alvo, para poder ser encadeado. Branches e histórico
permanecem intactos: `git worktree remove` descarta só o diretório de trabalho.

O contrato do script é exercitado em CI (job `limpeza-de-worktrees`) contra worktrees
descartáveis: um limpo (deve sumir), um sujo (deve ser bloqueado, com o arquivo pendente
preservado) e um inexistente (deve ser tolerado).

## 3 e 4. Registro de ambientes — a decisão humana vira dado versionado

`config/power-platform/environments.json` substitui "anote nome, ID e URL" por uma fonte
única revisada por PR. Ciclo de vida por ambiente:

```
NAO_DEFINIDO → DEFINIDO → CONEXAO_AUTORIZADA → PROMOCAO_VALIDADA
```

- `DEFINIDO`: `environment_url` + `environment_id` registrados (blueprint item 3);
- `CONEXAO_AUTORIZADA`: `connection_id` + `connection_reference_logical_name` registrados
  após o OAuth Teams (blueprint item 4);
- `PROMOCAO_VALIDADA`: exige `evidencia_run_url` da promoção real (blueprint item 5).

DEV não replica a URL: usa `url_secret_ref: POWER_PLATFORM_ENVIRONMENT_URL`, porque o valor
já vive no secret do environment `reqsys-power-platform-dev`. O registro **não** armazena
segredos — `connection_id` é identificador de recurso, não credencial.

`scripts/validar_ambientes_power_platform.py` bloqueia:

- URL fora de `https://<org>.crm<N>.dynamics.com` (inclusive barra final sobrando);
- `environment_id` / `connection_id` que não sejam GUID;
- `connection_reference_logical_name` fora do padrão `<prefixo>_<nome>` do Dataverse;
- status avançado com campo obrigatório vazio (ex.: `CONEXAO_AUTORIZADA` sem `connection_id`);
- dois ambientes lógicos apontando para a mesma URL, mesmo `environment_id` ou mesma conexão
  — o erro clássico de apontar TEST para DEV;
- `prod` marcado como `PROMOCAO_VALIDADA` antes de `test` — a ordem DEV → TEST → PROD é gate.

O validador também imprime a **próxima ação humana**, derivada do estado atual:

```
python scripts/validar_ambientes_power_platform.py
```

Hoje responde: *"Definir o ambiente Power Platform de TESTE e registrar environment_url +
environment_id."*

Para preencher TEST, abra um PR alterando apenas o bloco `test` do registro. O job
`registro-de-ambientes` valida no PR.

## 5. Promoção DEV → TEST — guarda de divergência

`teams-flow-bot-promotion.yml` ganhou um passo fail-closed antes do manifesto: os inputs
`environment_url_destino`, `connection_id_destino` e `connection_reference_logical_name` são
conferidos contra o registro do `ambiente_logico` escolhido. A promoção é bloqueada quando:

- o ambiente não está em `CONEXAO_AUTORIZADA` ou superior no registro; ou
- qualquer input digitado diverge do que foi registrado e revisado por PR.

A comparação é case-insensitive e as mensagens de erro **não** ecoam o valor registrado.

Consequência prática: um erro de digitação no `workflow_dispatch` não consegue mais promover
para o ambiente errado. Para destravar, corrija o registro por PR — não relaxe o gate.

Os demais bloqueadores da promoção real continuam de pé e são humanos: `REQSYS_API_SERVICE_TOKEN`
no environment `reqsys-power-platform-dev` (ver `docs/architecture/teams-flow-bot-promotion.md`)
e o ambiente TEST existente com Dataverse.

## 6. Segundo proprietário

Sem automação possível pelo repositório. O caminho curto do blueprint continua válido:
Power Automate → **My flows** → `robo_envia_teamsv2` → ⋮ → **Share** → adicionar a segunda
conta como **Owner**. Copropriedade não transfere credencial de conexão: a segunda identidade
precisa autorizar a própria conexão Teams. `Save As` só é necessário se a intenção for uma
cópia independente do fluxo, não para obter copropriedade.

## 7. Assinatura Azure

Adiado por decisão. Só entra em pauta se `flow_bot` for migrado para Azure Bot Service. Toda
assinatura Azure se vincula a exatamente um diretório Entra, então a validação, quando for a
hora, é a assinatura aparecer como **Active** no tenant `tieri659`.

## Ordem de execução

```
1. Renovar PAT  →  dispatch do watcher com enforce=true  →  #1130 encerrada
2. Limpar worktrees  (scripts/limpar-worktrees-orfaos.ps1)
3. Definir TEST no Power Platform  →  PR ajustando "test" para DEFINIDO
4. OAuth Teams no TEST  →  PR ajustando "test" para CONEXAO_AUTORIZADA
5. Promoção real DEV → TEST  →  PR registrando evidencia_run_url e PROMOCAO_VALIDADA
6. Segundo proprietário
7. Repetir 3–5 para PROD
8. Azure subscription somente se Azure Bot for aprovado
```

Os passos 1 e 2 são independentes dos demais e podem ser feitos em paralelo. Os passos 3 e 4
são o Pareto: destravam a primeira evidência real ponta a ponta, que hoje é o gap registrado
em `docs/architecture/teams-flow-bot-promotion.md`.
