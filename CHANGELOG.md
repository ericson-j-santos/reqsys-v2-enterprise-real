# Changelog

All notable changes to this project are documented in this file.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) — [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Unreleased] - 2026-09-04

### Corrigido (WSJF · `templates/wsjf/WSJF.xlsx.base64` era um ZIP corrompido, e era ele que ia para o tenant)

- Causa raiz do `unsupportedWorkbook` / `FileCorruptTryRepair` que impedia o fluxo Planner → Excel: o template canônico versionado no repositório — a origem do `WSJF.xlsx` enviado ao SharePoint por `scripts/bootstrap_wsjf_m365_dev.py` — não é um XLSX válido. O `PK\x05\x06` final aponta o diretório central 1836 bytes adiante do lugar real, o fluxo deflate de `xl/worksheets/sheet1.xml` está truncado no meio (`invalid distance too far back`) e o pacote não traz `docProps/core.xml` nem `docProps/app.xml`. O Excel de computador reconstrói o índice e abre normalmente; o motor Excel do Microsoft Graph — o mesmo usado pelo conector Excel Online (Business) — recusa o arquivo inteiro. Corrigir o gerador (#1475) não alcançava esse arquivo, porque ele não era gerado por ele.
- `templates/wsjf/WSJF.xlsx.base64` regenerado a partir de `wsjf_workbook_package.gerar_wsjf_xlsx()`. As 16 colunas e a ordem de `tbDemandas`, além do nome da aba (`Demandas`), foram recuperados de `xl/tables/table1.xml` do template anterior e preservados; o conteúdo das linhas era irrecuperável (fluxo deflate corrompido) e o template canônico é, como antes, vazio.
- `backend/wsjf_workbook_package.py` (novo): pacote canônico do `WSJF.xlsx`, validação estrita equivalente à do Graph (índice ZIP consistente, CRC de todas as partes, `docProps`, `tbDemandas` com suas colunas) e reparo que reescreve o arquivo com `openpyxl` preservando linhas e campos locais (`Risco`, `Próxima ação`, `Observações`) quando o pacote antigo ainda é legível.
- `scripts/bootstrap_wsjf_m365_dev.py`: `_validate_template` passou a usar a validação estrita — a checagem anterior só procurava o nome da tabela dentro do ZIP e por isso aprovou o template quebrado. Um `WSJF.xlsx` já existente no tenant deixa de ser reutilizado às cegas: é confrontado com o pacote e com `GET .../workbook/worksheets` e, quando recusado, é substituído no mesmo item (preservando o id que os fluxos já instalados referenciam), com cópia do arquivo anterior salva ao lado como `WSJF.incompativel-<UTC>.xlsx`.
- `POST /v1/hub-lowcode/wsjf/planner-excel/excel/diagnostico` e `.../excel/reparar` (novos): expõem esse diagnóstico e a substituição no instalador WSJF do ReqSys. `POST .../deploy` agora recusa instalar sobre uma planilha que o Graph rejeita — antes o fluxo era criado com sucesso e só falhava depois, em execução, longe do instalador. Falha de rede, permissão ou 5xx do Graph não bloqueiam a instalação: só a recusa do próprio pacote.
- `scripts/gerar_template_wsjf.py` (novo) regenera o template; `--check` falha se o arquivo versionado divergir do gerador e roda no workflow `bootstrap-wsjf-m365-dev`. `gerar_planilha_xlsx` passou a gravar com carimbo de tempo fixo, para que essa comparação seja possível.
- Testes: `backend/tests/test_wsjf_workbook_package.py` (10), `backend/tests/test_wsjf_excel_workbook_api.py` (8) e `tests/test_bootstrap_wsjf_m365_dev.py` (4), incluindo a reprodução do índice ZIP quebrado e a conferência de que as colunas de `tbDemandas` cobrem todos os campos que o fluxo escreve.

### Adicionado (Pentaho — Pareto na cobertura de testes de `PentahoIntegracoesView.vue`)

- `frontend/tests/e2e/pentaho-integracoes.spec.js`: de 1 para 8 cenários, priorizados por Pareto — erro do backend ao carregar o painel (com e sem `detail` do backend, este último via queda de rede real), erro 409 ao reprocessar um lote fora de quarentena (continuação direta do Pareto do backend em `test_pentaho_integration_api.py`), estados vazios (nenhum processo/lote), status não mapeado sem quebrar a tela, ausência do botão Reprocessar fora de `QUARENTENA`, e recarregamento manual pelo botão Atualizar. Nenhum desses caminhos de erro/estado tinha teste antes — só o caminho feliz.
- Corrigido o teste original (`getByText('Quarentena').last()`), que colidia com um tooltip de navegação teleportado ("Acompanhar lotes, processamento, quarentena e reprocessamento") introduzido por uma correção de acessibilidade não relacionada (#1482) — passou a ficar flaky/quebrado. Escopado para dentro de `[data-testid="route-integracoes-pentaho"]` com `exact: true`.
- **Gotcha de ambiente, não de produto:** ao validar isso localmente via Git Bash, `VITE_API_URL=/api npm run dev` fazia o MSYS reescrever `/api` para um caminho Windows (`C:/Program Files/Git/api`) antes do Node ver a variável, quebrando toda chamada Axios da página sem nenhum erro de rede visível (a exceção nunca chegava a um XHR real). Não afeta CI/produção (não usam Git Bash para isso), mas vale registrar para quem for depurar este componente localmente no Windows.

### Adicionado (Power Platform — automação do que era acionável no blueprint de ações humanas)

- `config/power-platform/environments.json`: registro versionado de DEV/TEST/PROD, substituindo anotações soltas de "nome, Environment ID e URL Dataverse" por fonte única revisada em PR. Ciclo de vida `NAO_DEFINIDO → DEFINIDO → CONEXAO_AUTORIZADA → PROMOCAO_VALIDADA`, espelhando os itens 3, 4 e 5 do blueprint. DEV não replica a URL: usa `url_secret_ref: POWER_PLATFORM_ENVIRONMENT_URL`, mantendo o valor no secret. `connection_id` é identificador de recurso, não credencial — nenhum segredo é armazenado.
- `scripts/validar_ambientes_power_platform.py` (+ `tests/test_validar_ambientes_power_platform.py`, 19 casos): bloqueia URL fora de `https://<org>.crm<N>.dynamics.com`, `environment_id`/`connection_id` não-GUID, `connection_reference_logical_name` fora do padrão Dataverse, status avançado com campo obrigatório vazio, dois ambientes lógicos apontando para o mesmo recurso (o erro clássico de apontar TEST para DEV) e `prod` validado antes de `test`. Imprime a próxima ação humana derivada do estado atual.
- `scripts/limpar-worktrees-orfaos.ps1`: automatiza a limpeza dos 11 worktrees órfãos de forma idempotente e fail-closed — **nunca** usa `git worktree remove --force`, recusa worktree com arquivos não commitados ou commits ausentes do upstream (dizendo o que segurou), roda `prune`, reconfere a lista e grava `artifacts/governance/worktree-cleanup.json`. Não executa `checkout`, `reset` ou `stash`, respeitando o guardrail do `CLAUDE.md`.
- `.github/workflows/power-platform-promotion-readiness-contract.yml`: valida o registro em PR e exercita o limpador contra worktrees descartáveis (limpo removido, sujo bloqueado com o arquivo pendente intacto, inexistente tolerado, branches preservados).
- `docs/runbooks/acoes-humanas-power-platform.md`: mapa honesto das 7 ações — o que virou código e o que continua inevitavelmente manual (OAuth Teams, geração do PAT, escolha dos ambientes, segundo proprietário).

### Corrigido (Promoção Teams Flow Bot e aceite da credencial #1130)

- `.github/workflows/teams-flow-bot-promotion.yml`: o job não tinha `actions/checkout`, então nenhum script do repositório estava disponível em runtime. Adicionado, junto com um passo fail-closed que confere `environment_url_destino`, `connection_id_destino` e `connection_reference_logical_name` contra o registro antes de promover. Um erro de digitação no `workflow_dispatch` deixa de conseguir promover para o ambiente errado; a comparação é case-insensitive e as mensagens não ecoam o valor registrado.
- `.github/workflows/github-workflow-permission-readiness-watch.yml`: o critério de conclusão da issue #1130 é "watcher publica evidência e **encerra** esta issue", mas o passo `Record first validated credential readiness` só comentava — o aceite ficava manual para sempre, mesmo com a credencial validada. Agora encerra a issue com `state_reason: completed`, de forma idempotente (verifica o estado antes) e sem impedir o encerramento quando o comentário já existe.

## [Unreleased] - 2026-09-03

### Adicionado (Integração Pentaho→ReqSys — Pareto na cobertura de testes do adaptador de lotes)

- `backend/tests/test_pentaho_integration_service.py` (novo, 6 casos) e 4 casos novos em `test_pentaho_integration_api.py`: fecham as lacunas de maior risco entre os controles já documentados em `docs/architecture/pentaho-reqsys-adapter.md` mas sem teste — corrida de idempotência resolvida via `IntegrityError` real (não só a checagem prévia), reprocessamento restrito a `QUARENTENA` (409 fora disso), limite de registros por lote (413), aceitação parcial de um lote com registros válidos e vazios misturados (as suítes anteriores só cobriam tudo-aceito ou tudo-rejeitado), validação de parâmetros de `recuperar_lotes_abandonados`, e 404 de lote inexistente. Ver tabela completa em `docs/architecture/pentaho-reqsys-adapter.md#cobertura-de-testes-pareto-2026-09-03`.
- Extraído `_buscar_lote_por_idempotencia` em `backend/app/services/pentaho_integration.py` (elimina duplicação entre a checagem inicial e o fallback de `IntegrityError`, e cria o ponto de inserção usado para simular a corrida no teste acima).

### Adicionado (Gerador Pentaho — Pareto na cobertura de testes do fluxo de dossiê)

- `tools/gerador_pentaho/pacote/testes/fluxo.test.js`: de 2 para 8 casos, priorizados por Pareto para cobrir os 5 estados finais documentados (`DOSSIÊ_CRIADO`, `CRIAÇÃO_RECUSADA`, `RESPOSTA_INVÁLIDA`, `AUTENTICAÇÃO_RECUSADA`, `FALHA_TÉCNICA`) e os critérios de aceite de retentativa/timeout de `pacote/docs/mapeamento-pentaho.md` (5xx intermitente retentado e sucede, 4xx não retentado, 5xx persistente esgota `MAX_TENTATIVAS` e não insiste além do limite) — nenhum desses tinha teste antes. Ver análise completa em `docs/servicos/gerador-pentaho-dossie.md`.
- Corrigido `node --test testes/fluxo.test.js` executado diretamente dentro do repositório: a raiz do monorepo declara `"type": "module"` em `package.json`, herdado por qualquer `.js` sem `package.json` mais próximo, quebrando com `ReferenceError: require is not defined`. Nunca apareceu em CI porque o workflow só testa via `--output` do CLI (fora da árvore do repo). Corrigido com `tools/gerador_pentaho/pacote/package.json` (`"type": "commonjs"`).

### Adicionado (Gerador Pentaho — fluxo de dossiê trazido ao padrão ouro do repositório)

- `tools/gerador_pentaho/`: aplicação de treinamento de fluxo de criação de dossiê (Node.js + job/transformações Pentaho Data Integration 7.1+, `pentaho/*.kjb`/`*.ktr`), antes mantida solta fora do repositório como `gerador_solucao_completa_v2.1.0.py` — um script que embarcava toda a aplicação como blob base64 validado contra um SHA-256 fixo. Trazida para dentro do controle de versão como arquivos reais em `tools/gerador_pentaho/pacote/` (revisável em PR, diffável, testável), com `gerador_solucao_completa.py` reduzido a um empacotador (`--dry-run`/`--output`/`--force`/`--zip`/`--run-tests`) no mesmo padrão CLI dos demais geradores do repositório (`tools/geradores/gerar_servicos_email_teams.py`).
- Dados exclusivamente sintéticos (ADR-002/LGPD) — sem segredo, CPF, e-mail real ou endpoint interno; varrido e confirmado antes da migração.
- Testes: `tests/test_gerador_pentaho.py` (pytest, 7 casos — listagem, geração de diretório byte-idêntica à fonte, falha sem `--force`, sobrescrita com `--force`, geração de ZIP com prefixo/conteúdo corretos, ausência de termos de segredo) e `tools/gerador_pentaho/pacote/testes/fluxo.test.js` (`node --test`, 2 casos — criação de dossiê e recusa de regra de negócio), este último executável também via `--run-tests` do CLI.
- Novo workflow `.github/workflows/gerador-pentaho-dossie-validation.yml`, disparado em qualquer alteração em `tools/gerador_pentaho/**`: roda os testes pytest, o `--dry-run`, gera a aplicação e roda os testes Node.js de ponta a ponta.
- Documentação: `tools/gerador_pentaho/README.md` (uso do CLI) e `docs/servicos/gerador-pentaho-dossie.md` (origem, decisão técnica, testes aplicados).

## [Unreleased] - 2026-08-27

### Corrigido (GovBI IA · endpoint Gemini incorreto quebrava o provider primário)

- `LLMGateway.gerar_gemini` (`backend/app/services/llm_provider.py`) chamava `POST https://generativelanguage.googleapis.com/v1beta/interactions` — endpoint inexistente na API real do Gemini — com payload `{model, input, generation_config}`. Toda chamada ao Gemini falhava com `404 Not Found`, era classificada (incorretamente) como "modelo indisponível" e o sistema caía sempre para o fallback Groq, mascarando o problema. Confirmado ao vivo via `POST /v1/ia/govbi/probes` em `reqsys-api-dev`/`reqsys-api.fly.dev` e traceback em `fly logs`.
- Corrigido para o contrato real `generateContent`: `POST /v1beta/models/{model}:generateContent` com payload `{contents: [{parts: [{text}]}], generationConfig, systemInstruction}`. `extrair_resposta_gemini` já esperava esse formato de resposta (`candidates[].content.parts[].text`) — só a montagem da requisição estava errada.
- `tests/test_llm_provider_service.py::test_gateway_gemini_monta_payload_padrao` antes afirmava a URL/payload quebrados (por isso o bug não foi pego pela suíte de testes, que só mocka a chamada HTTP); atualizado para validar o contrato correto.
- **Gap remanescente, fora do que código pode corrigir:** com o Gemini corrigido, o probe passou a expor uma falha real e distinta no Groq (`403 Forbidden` em `api.groq.com`) — indica `GROQ_API_KEY` inválida/revogada ou sem permissão para o modelo `llama-3.3-70b-versatile` nos ambientes `reqsys-api-dev`/`reqsys-api` (Fly secrets). Requer verificação/rotação da chave no console Groq por um humano; não há evidência de bug de código nesse lado.

---

## [Unreleased] - 2026-08-26

### Adicionado (Planner · contrato governado + idempotência, issue #32)

- Novo caminho aditivo e paralelo ao `POST /v1/hub-lowcode/planner/tasks` existente (texto livre, sem idempotência, permanece intocado): `backend/app/services/planner_publish.py` + modelo `PlannerPublishAttempt` (`backend/app/models/planner_publish_attempt.py`) — publica uma tarefa por chamada via contrato único `PublishPlannerTaskRequest`/`PublishPlannerTaskResponse` (`backend/app/schemas/planner_publish.py`), com idempotência garantida por constraint UNIQUE em `idempotency_key = sha256(f"{source_id}|{sha256(payload_ordenado)}")` — reenviar a mesma tarefa retorna `status: "duplicado"` sem criar uma segunda tarefa no Planner.
- Status padronizado por tentativa: `enfileirado`/`publicado`/`duplicado`/`falhou_validacao`/`falhou_integracao`; falhas de validação (ex. `priority` fora do conjunto aceito) não persistem tentativa, só log.
- 4 rotas novas em `backend/app/api/hub_lowcode.py`: `POST /v1/hub-lowcode/planner/publish`, `GET /v1/hub-lowcode/planner/publish/{id}`, `GET /v1/hub-lowcode/planner/publish` (lista, filtrável por `source_id`/`status`), `POST /v1/hub-lowcode/planner/publish/{id}/reprocessar` — todas protegidas por `require_admin_or_service_token('planner_publish:enviar')` (o endpoint legado de texto livre continua sem auth, gap pré-existente fora de escopo aqui).
- Reprocessamento seguro: só permitido para tentativas em `falhou_integracao`, rejeita (`409`) tentativas já `publicado`/`duplicado` e acima de `MAX_TENTATIVAS_REPROCESSO=5`; nunca reenvia uma tarefa já criada no Planner.
- Mascaramento de segredo (`x-webhook-key`/`Bearer`) em qualquer erro persistido, e auditoria via `registrar_evento` (ADR-003) em toda publicação/reprocessamento.
- Migração `backend/alembic/versions/7a1c9e4b2d6f_planner_publish_attempts.py` (tabela `planner_publish_attempts`).
- Testes: `backend/tests/test_planner_publish_service.py` (11 casos: sucesso, duplicidade, payload distinto, webhook não configurado, erro HTTP mascarado, validação, reprocessamento e seus limites) e `backend/tests/test_planner_publish_api.py` (8 casos: contrato, auth, 404, 409).
- Fora de escopo deste incremento (ver issue #32): UI de status no frontend, alinhamento com `reqsys-powerplatform-alm`/`reqsys-java-platform` (repos não presentes neste workspace), reprocessamento automático agendado.

---

## [Unreleased] - 2026-07-23

### Adicionado (Redmine Sync Queue · fecha o loop do fluxo PA-001-CreateRedmineIssue)

- Novo worker `backend/app/services/redmine_sync_queue.py` + adapter genérico `backend/app/services/dataverse_queue_client.py` (Dataverse Web API OData, token client-credentials, resolução de `EntitySetName` via Metadata API — nunca adivinha pluralização): lê `cr85a_redminequeue` (`Status=PENDING`), cria a issue real no Redmine (`github_redmine.criar_issue_generica`, reaproveitando o adapter/retry/circuit breaker já existentes) e grava o resultado de volta em `cr85a_redminequeue` + `cr85a_agilesync` + `cr85a_auditlog` — o pedaço que faltava porque o conector HTTP genérico do Power Automate está bloqueado por DLP nesse tenant.
- `POST /v1/redmine-sync/processar` (JWT admin ou `X-Service-Token` escopo `redmine_sync:processar`), `GET /v1/redmine-sync/status`, `GET /v1/redmine-sync/diagnostico/coluna` em `backend/app/api/redmine_sync.py`.
- Limpeza automática de reservas travadas (`PROCESSING` > `REDMINE_SYNC_RESERVA_TIMEOUT_MINUTOS`, padrão 15 min) antes de reservar novo lote, com log/auditoria `QUEUE_RESERVATION_TIMEOUT_RECOVERED`; limite de tentativas (`REDMINE_SYNC_MAX_TENTATIVAS`, padrão 5) evita retry infinito; `dry_run` com formato de resposta deliberadamente distinto de um envio real; mascaramento de segredo (`X-Redmine-API-Key`/`Bearer`) em qualquer erro persistido.
- `GET /v1/redmine-sync/diagnostico/coluna` automatiza o diagnóstico pendente do usuário para o erro "String or binary data would be truncated" em `cr85a_agilesync.cr85a_correlationid` — consulta a Metadata API do Dataverse ao vivo e retorna `attribute_type`/`max_length` reais, com alerta explícito quando o campo é curto demais para um `guid()` (36 caracteres).
- Novas settings em `.env`/`config.py`: `REDMINE_SYNC_DATAVERSE_URL`, `REDMINE_SYNC_LOTE_MAX`, `REDMINE_SYNC_RESERVA_TIMEOUT_MINUTOS`, `REDMINE_SYNC_MAX_TENTATIVAS`.
- Documentação viva em `docs/architecture/redmine-sync-queue.md`: diagrama do fluxo completo, estado atual x alvo x gaps, colunas novas ainda necessárias em `cr85a_redminequeue` (`cr85a_reservedat`, `cr85a_retrycount`, `cr85a_errordetail`, `cr85a_redmineissueid` opcional) e por que o processamento é sob demanda, não um poll automático contínuo (ADR-011).
- 25 novos testes (`test_redmine_sync_queue_service.py`, `test_redmine_sync_api.py`, `test_dataverse_queue_client.py`), todos mockados.
- `scripts/configurar_redmine_sync_queue.py` (novo, mesmo espírito de `scripts/configurar-redmine.ps1`/`verificar-redmine.ps1`): captura interativamente (`capturar`) as credenciais reais que faltam (`AZURE_*`, `REDMINE_*`, `REDMINE_SYNC_DATAVERSE_URL`) e valida tudo ao vivo (`verificar`) — token Azure AD/Dataverse, Application User do `AZURE_CLIENT_ID` no ambiente, schema real de `cr85a_redminequeue`/`cr85a_agilesync`/`cr85a_auditlog` contra o assumido no código (incluindo o diagnóstico do bloqueador `cr85a_correlationid`), e conectividade de leitura com o Redmine. Novas funções de suporte em `dataverse_queue_client.py`: `testar_autenticacao`, `verificar_application_user`, `listar_colunas`.
- Também corrige `scripts/configurar-redmine.ps1`: o script lia `data[].nome`/`.status` de `/v1/sistema/segredos-status`, mas o endpoint real responde `data.segredos[].name`/`.resolved` (booleano) — a verificação de sucesso nunca refletia o estado real.
## [Unreleased] - 2026-07-26

### Adicionado (Migração rotina de e-mail Prospecção Movimento · #2861 · DDL das views de origem)

- `backend/app/services/movimento_email/sql/views/`: artefato de banco **versionado e autocontido** (ADR-012) para as 4 views de origem — `V1__vw_prospeccao_movimento_{fechamento_diario,pendencias_cadastro,pendencias_historicas,pendencias_observacao}.sql` (idempotentes via `CREATE OR ALTER VIEW`), `V1__rollback.sql` (`DROP VIEW IF EXISTS`), `MANIFEST.json` (SHA-256 por arquivo — versão publicada é imutável, mudança vira `V2`) e `README.md` com a convenção de versionamento.
- `scripts/aplicar_movimento_email_views.py` (`status`/`aplicar --dry-run`/`aplicar`/`rollback --confirmar`): runner autocontido (stdlib + `pyodbc`, sem Flyway/Liquibase) que valida os checksums contra `MANIFEST.json` antes de tocar no banco, aplica dentro de uma única transação com rollback automático em falha, e nunca remove views sem `--confirmar` explícito.
- Gap #1 (docs/architecture/movimento-email-pipeline.md) **restrito, não fechado**: a DDL das 4 views já é real, idempotente e deployável hoje — mas o corpo de cada uma é um stub `SELECT ... WHERE 1 = 0` com o contrato de colunas exato que `repository.py`/`models.py` esperam, porque o `FROM`/`JOIN` real contra o schema legado do SSRS ainda depende de confirmação da equipe de dados (exemplo do `SELECT` real já deixado comentado em cada arquivo).
- `tools/geradores/movimento_email_autocontido.py`: tradução autocontida de todo o pipeline (mesmo padrão de `robo_envia_teamsv1_autocontido.py`) em um único arquivo — só stdlib + `pyodbc` (extração), fila durável via `sqlite3` local em vez de SQLAlchemy/MongoDB, HTML renderizado sem Jinja2 (string building + `html.escape`). CLI `job`/`consumir`/`status`/`dashboard`; payload completo também publicado em base64 (`movimento_email_autocontido.py.b64`).
- `ops-dashboard/movimento-email/index.html`: dashboard autocontido (sem CDN externo, mesmo padrão de `ops-dashboard/teams-notification/`) — cards por status (PENDING/PROCESSING/SENT/ERROR), badge de saúde (verde/azul/vermelho/cinza — ADR-007) e tabela de itens recentes, consumindo `./data.json`; nunca publica `html_body`/destinatários completos. `data.json` é gerado sob demanda por `movimento_email_autocontido.py dashboard --output ...` (novo comando; `construir_dashboard_data`/`classificar_saude`/`listar_recentes` são funções puras, testáveis sem I/O).
- 26 novos testes (`tests/test_movimento_email_autocontido.py`, padrão `unittest` + `importlib`, mesmo estilo de `test_robo_envia_teamsv1_autocontido.py`): renderização/escaping, mascaramento, retry + circuit breaker, `classificar_saude`, `construir_dashboard_data`, máquina de estados da fila sqlite (reserva/timeout/retry), integridade estrutural do dashboard HTML (sem CDN, consome `./data.json`, não vaza dado sensível) e `cmd_dashboard` fim a fim.
- **Bug real encontrado e corrigido pelos testes**: `reservar_lote` devolvia `sqlite3.Row` capturadas *antes* do `UPDATE` (status ainda `PENDING` no objeto retornado, mesmo com a linha já `PROCESSING` no banco) — `sqlite3.Row` é uma cópia estática, não uma view viva. Corrigido para re-buscar as linhas após o `commit`. Payload base64 regenerado após a correção.

## [Unreleased] - 2026-07-24

### Adicionado (Migração rotina de e-mail Prospecção Movimento · #2861)

- Novo pipeline `backend/app/services/movimento_email/`: extração (`repository.py`, pyodbc + retry + circuit breaker, SQL externalizado em `sql/*.sql`), transformação (`transform.py`, função pura), renderização HTML/texto (`email_service.py` + `templates/email_movimento.html`, Jinja2 com autoescape), fila durável (`queue_repository.py`, tabela `movimento_email_dispatch`) e consumer (`consumer.py`) — substitui o modelo antigo SSRS/agendamento nativo por Python de ponta a ponta.
- `POST /v1/movimento-email/jobs/executar` (extrai + renderiza + enfileira), `POST /v1/movimento-email/fila/consumir` (envia via SMTP), `GET /v1/movimento-email/status` (contagem por status) em `backend/app/api/movimento_email.py`; autenticação JWT admin ou `X-Service-Token` escopado (`movimento_email:job`/`movimento_email:consumir`).
- Limpeza automática de reservas travadas (`PROCESSING` > `MOVIMENTO_EMAIL_RESERVA_TIMEOUT_MINUTOS`, padrão 15 min) antes de reservar novo lote, com log quando libera (instrução global do usuário); limite de tentativas (`MOVIMENTO_EMAIL_MAX_TENTATIVAS`, padrão 5); `dry_run` com formato de resposta deliberadamente distinto de um envio real (nunca parece, estruturalmente, um sucesso real).
- Novas settings em `.env`/`config.py`: `MOVIMENTO_EMAIL_SOURCE_DSN`, `MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS`, `MOVIMENTO_EMAIL_SMTP_HOST/PORT/USER/PASSWORD/USE_TLS/FROM`, `MOVIMENTO_EMAIL_RECIPIENTS`, `MOVIMENTO_EMAIL_LOTE_MAX`, `MOVIMENTO_EMAIL_RESERVA_TIMEOUT_MINUTOS`, `MOVIMENTO_EMAIL_MAX_TENTATIVAS`.
- Documentação viva em `docs/architecture/movimento-email-pipeline.md`: diagrama do fluxo, decisão de usar a fila SQLAlchemy já provisionada em vez de introduzir MongoDB sem credenciais, estado atual x alvo x gaps — principal gap: os 4 SELECTs de origem (`fechamento_diario.sql`, `pendencias_cadastro.sql`, `pendencias_historicas.sql`, `pendencias_observacao.sql`) usam nomes de view placeholder até confirmação da equipe de dados.
- 27 novos testes (`test_movimento_email_transform.py`, `test_movimento_email_template.py`, `test_movimento_email_queue_repository.py`, `test_movimento_email_consumer.py`, `test_movimento_email_jobs.py`, `test_movimento_email_api.py`) — extração real (pyodbc) e envio real (SMTP) não testados nesta sessão por falta de credenciais/DSN.


## [Unreleased] - 2026-07-27

### Corrigido (Teams Gateway · contrato de resposta)

- `tools/geradores/teams_graph_gateway_autocontido.py`: `send_webhook` agora envia `eventType` (padrão `"commit-notification"`) no payload e valida a resposta HTTP do fluxo de destino (`_validar_contrato_resposta`) — rejeita (`GatewayError`) quando a resposta ecoa explicitamente um `correlationId` ou `eventType`/`type` diferentes dos enviados, evitando que um roteamento incorreto no Power Automate (ex.: cartão estático de outro fluxo) seja reportado como sucesso pelo CI. Tolerante quando o fluxo não ecoa esses campos.
- Diagnóstico investigado nesta correção: o cartão estático "Requisito #482" já havia sido corrigido no fluxo `robo_envia_teamsv2` em sessões anteriores (2026-07-26); um dry-run ao vivo confirmou que o corpo do cartão já está dinâmico. Esta mudança adiciona a proteção de contrato pedida como camada adicional, não uma reaplicação da correção do cartão em si.
- `docs/servicos/teams-commit-notification.md`: documenta o novo campo `eventType` e o contrato de resposta.

## [Unreleased] - 2026-07-14

### Adicionado (Teams Gateway · notificações automáticas)

- `scripts/notificar_teams.py`: wrapper stdlib (sem dependências externas) para `POST /v1/teams-gateway/messages`, reutilizável por qualquer automação/CI; escreve evidência JSON (`--output`) e não derruba o build por padrão em caso de falha de entrega (usar `--strict` para propagar erro).
- `.github/workflows/notify-teams-repo-changes.yml`: notifica o Teams a cada push em `main` com autor/mensagem/link do commit.
- `deploy-production-sync.yml` e `fly-enterprise-sync.yml`: job `summary` passa a notificar o Teams com o resultado da implantação/sincronização por ambiente (produção sempre; demais ambientes só quando uma implantação real foi executada via `workflow_dispatch`).
- Requer o secret de repositório `TEAMS_GATEWAY_DESTINO_ID` (e-mail/UPN do destinatário) configurado no GitHub Actions — ver `docs/architecture/teams-messaging-gateway.md`.
- **Produção**: registrado o primeiro `flow_bot_owner` real (reaproveitando o fluxo Power Automate já validado) via `POST /v1/teams-gateway/flow-bot/owners`; canal `flow_bot` confirmado `disponivel=true` e testado com envio real (`entregue: true`).

## [Unreleased] - 2026-07-05

### Adicionado (Financeiro · CDI)

- Provedor interno e gratuito da taxa CDI diária (`backend/app/services/cdi_provider.py`, `backend/app/models/cdi_rate.py`): Banco Central (série SGS 12) como fonte primária, com cache local em `cdi_rates` e fallback para o último valor conhecido (`stale=true`) quando o BCB está indisponível. Endpoints `GET /v1/financeiro/cdi/latest` e `POST /v1/financeiro/cdi/refresh` (admin) em `backend/app/api/financeiro.py`. Fonte registrada e auditada em `config/external-sources-registry.json` (`bcb-sgs-cdi`).
- `backend/app/core/resilience.py`: `CircuitBreaker` + `call_with_retry` genéricos (retry exponencial + circuit breaker com cooldown), extraídos do provedor de CDI para reuso em qualquer adapter externo. `cdi_provider.py` foi migrado para usá-los; nenhum outro adapter foi migrado ainda (gap pendente, ver runbook).
- Auditoria (`registrar_evento`) em `POST /v1/financeiro/cdi/refresh`: eventos `CDI_REFRESH_SUCESSO`/`CDI_REFRESH_FALHA` com `correlation_id` e usuário admin responsável.
- Frontend (`frontend/src/views/FinanceiroView.vue`, `frontend/src/services/financeiro.js`): página `/financeiro` com cards de taxa diária (% e decimal), status de cache (atualizado/desatualizado) e drill-down de fonte/URL/fórmula; botão "Atualizar do Banco Central" visível apenas para `papel === 'admin'`. Rota e item de menu registrados em `router/index.js` e `constants/navCatalog.js`.
- `scripts/scaffold_cdi_feature.py`: gerador autocontido (stdlib apenas) que escreve em disco todos os arquivos da feature CDI (backend + testes + frontend) a partir de templates embutidos — reprodutível em qualquer checkout do repositório. Ver `docs/FINANCEIRO_CDI.md`.
- `docs/FINANCEIRO_CDI.md`: documentação viva da feature (estado atual, estado alvo, gaps pendentes, como operar e como reproduzir via scaffold).

## [Unreleased] - 2026-07-03

### Corrigido (crítico — implantação, parte 2)

- Mesmo bug do `configurar_fly_auth_azure.py` encontrado em mais 2 lugares durante auditoria: `scripts/validar_login_multi_ambiente.py` (chamada de `validar_config` no step "Validar sync pós-deploy" — fazia o `deploy-production-sync.yml` reportar `failure` mesmo com a implantação da API já bem-sucedida) e `.github/workflows/deploy-staging-auth-fix.yml`/`auth-azure-operational-gate.yml` (valor de `--expected-redirect-uri` sem o sufixo `/auth/callback.html`). Corrigidos todos; teste de regressão adicionado em `tests/scripts/test_validar_login_multi_ambiente.py`.

### Corrigido (crítico — implantação)

- `scripts/configurar_fly_auth_azure.py`: a validação pós-deploy comparava `expected_redirect_uri` (que a API sempre publica como `{app_public_url}/auth/callback.html`, ver `app/core/config.py:azure_expected_redirect_uri`) contra `app_public_url` puro, sem o sufixo — uma igualdade que nunca poderia ser verdadeira. Isso fazia o job "Configurar secrets auth produção" falhar sempre, bloqueando "Deploy API produção" (`needs: configure-prod-secrets`) em `deploy-production-sync.yml`. Confirmado que isso vinha bloqueando implantações de backend desde pelo menos 2026-07-02 00:07 — a API em produção estava rodando o commit do PR #654, **28 commits atrás do `main`**, sem nenhuma das mudanças de backend desta sessão. Corrigido comparando contra `{app_public_url}/auth/callback.html`. Teste de regressão em `tests/test_configurar_fly_auth_azure.py`.

### Adicionado (pipeline de requisitos)

- `POST /v1/requisitos/concluir/{id}`: o pipeline (`recebido → validado → estruturado → backlog`) não tinha nenhuma transição formal para um estado terminal — itens entregues ficavam presos em `backlog` sem trilha de auditoria de fechamento. Novo endpoint fecha um requisito em `backlog` como `concluido`, exige `evidencia` objetiva e `responsavel` no payload (nunca fecha por inferência) e registra evento de auditoria `REQUISITO_CONCLUIDO` com `correlation_id`. Testes em `test_pipeline_api_critical_paths.py`.

### Corrigido

- `requisitos_metricas.py`: status `backlog` (alcançado via `POST /v1/backlog/publicar-redmine`, estágio posterior a `estruturado`) era contado como "pendente" no cálculo de Qualidade IA, penalizando requisitos já triados e publicados como se estivessem intocados. Adicionado a `STATUS_EM_ANALISE`, junto com `scripts/relatorio_qualidade_ia_pendentes.py` (cópia sincronizada). Validado ao vivo: score de produção sobe de 58.25 para 77.25 sem alterar nenhum dado, só a classificação.

### Alterado

- GitHub Environment `production`: gate nativo `required_reviewers` (`ericson-j-santos`) + `deployment_branch_policy` restrito a `main`, substituindo o hack de string `APROVO-PROD`. Aplicado via API (não versionado como código); comandos de reprodução documentados em `docs/runbooks/producao-flyio-pendencias.md`.

### Corrigido

- `styles.css`: `v-card` renderizado dentro de `v-overlay` (diálogos, ex. "Novo requisito" e o detalhe de requisito) ficava com fundo quase transparente (`rgba(255,255,255,0.02)`), pois a regra global de card "vidro" tinha `!important` sem exceção para overlays. Adicionada regra `.v-overlay .v-card` com fundo opaco e sombra, sem alterar a aparência dos cards de conteúdo normal da página. Validado com Playwright/screenshot antes e depois em dois diálogos.

### Adicionado

- `RequisitosView.vue`: linhas da tabela "Analítico de requisitos" ficam clicáveis e abrem um diálogo com o detalhe completo do requisito (título, código, status, descrição, urgência, área, sistema, solicitante, impacto regulatório), usando os dados já carregados na listagem — sem chamada de rede adicional.
- `scripts/relatorio_qualidade_ia_pendentes.py`: relatório somente-leitura que lista, por ambiente (dev/hml/prod), os requisitos fora das categorias aprovado/em_analise/rejeitado — a causa raiz real do score de Qualidade IA baixo, sem mascarar ou alterar dados.
- `scripts/replicate_requisitos_anonimizado.py`: replicação on-demand (`--execute`, dry-run por padrão) de requisitos de produção para hml/dev, mascarando `solicitante` com pseudônimo estável (LGPD) e marcando origem para reexecução idempotente. Escopo deliberadamente limitado a `requisitos`; não replica `auditoria` nem `recommendation_ia`, para não contaminar a trilha de auditoria de cada ambiente.
- `.github/workflows/qualidade-ia-snapshot.yml` + `scripts/registrar_qualidade_ia_snapshot_ci.py`: snapshot diário agendado de Qualidade IA em dev/hml/prod via `POST /v1/qualidade-ia/snapshot`, com aviso automático (`::warning`) quando `score_geral < 70`.
- `docs/runbooks/qualidade-ia-e-replicacao-ambientes.md`: runbook consolidando o diagnóstico do score de Qualidade IA e o procedimento de replicação anonimizada entre ambientes.

## [Unreleased] - 2026-07-02

### Adicionado

- LowCode Solution Factory P0 (`backend/app/services/lowcode_solution_factory.py`, `backend/app/schemas/lowcode_solution.py`): gera blueprint completo de solution Power Platform (Dataverse, Canvas App, Power Automate, Copilot Studio, security roles, pacote ALM zipado) em modo `dry_run` por padrão, sem escrita externa. Endpoints `POST /v1/hub-lowcode/solutions/generate` e `/solutions/generate/canvas`.
- `scripts/prod_readiness_audit.py`: checagem opcional `--check-azure-entra` que confirma via `az ad app show` se o redirect URI SPA já está registrado no Microsoft Entra ID, reduzindo a dependência de evidência humana manual; `production_environment` agora aceita aliases (`production`, `prod`, `prd`, `producao`, `produção`).

### Alterado

- Produção Fly.io: `CORS_ORIGINS` da API passa a incluir `https://tieriprod.duckdns.org`; `frontend/fly.toml` fixa `min_machines_running = 1` para evitar cold start no app público.
- Padronização de `.github/PULL_REQUEST_TEMPLATE.md` para `.github/pull_request_template.md` e de `ci-e2e.yml` para `ci-e2e-governado.yml`, refletido em `governanca-padrao-ouro.yml`, `pr-governed-ci-validation.yml` e nos índices de documentação (ADR-0001, PADRAO_OURO_ENTERPRISE, LIVING_ARCHITECTURE_INDEX, artifact-contracts-index).

- Application Balance Scorecard v0.1.0 em `docs/ops-dashboard/application-balance-scorecard.md` e `docs/ops-dashboard/data/application-balance-scorecard-v0.1.0.json`, consolidando domínios de equilíbrio, pesos, semáforo, evidência esperada, guardrails e caminho Pareto para estabilizar frontend, runtime, API, CI/CD, governança, documentação e segurança.
- Operational Evidence Hub em `docs/dashboard/operational-evidence-hub.html` consolidando delivery readiness, completion, finalization, maturity snapshot, observability correlation, artifact contract validation, dashboard regression validation e living architecture traceability com cards executivos, drill-down navegável, semáforo, confidence level, operational risk e fallback governado para artifacts ausentes.
- Runbook `docs/runbooks/operational-evidence-hub.md` e atualização dos índices de rastreabilidade (`living-architecture-map.json`, `command-center-evidence-index.md`, `command-center-navigation-map.md`, `operational-command-center.md`).
- Validação estática ampliada em `scripts/validate-dashboard-regression.mjs` para o Evidence Hub (cards, fontes JSON, drill-down, fallback e indicadores de governança).

- REQSYS#326: Runtime Observability Foundation com correlation analytics, topology preview, readiness de observabilidade e artifacts lógicos `runtime-correlation-report.json`/`runtime-observability-report.json` nos endpoints runtime.
- REQSYS#325: Smoke validator público com `ops-readiness-report.json`, validação opcional de frontend/runtime dashboard/incidentes/CORS, readiness consolidado e integração do status Fly/DuckDNS ao Ops Dashboard.
- REQSYS#323: Ops Dashboard com drill-down por domínio, detalhes de health/evidence/risk/environment drift/governance, Incident Timeline local filtrável e integração opcional de `runtime-health-report.json` e `runtime-operational-evidence-graph.json`.
- Runtime Health Center P2 (`schema_version=1.1.0`) com ingestão local de artifacts, consolidação de evidence graph/risk scoring/PR Evidence Gate e detector de drift entre dev/test/prod refletido em `maturity_percent` e `operational_risk`.
- Consolidação do Runtime Operacional Autônomo Governado no `scripts/runtime_health_validator.py`, com status executivo, maturidade operacional, backlog automático, detecção de regressão, rollback governado, sincronização Fly.io e evidência navegável.
- Runtime Health Validator `schema_version=1.2.0`: health matrix, runtime score canônico, quarantine (`AOP-SEC-QUARANTINE-001`), retry policy governada (`AOP-CI-RETRY-001`), fallback progressivo (API → cache → baseline) e propagação de `runtime_score` no Coordenador Status Consolidator.
- ADR e documentação operacional do runtime em `docs/adr/ADR-034-autonomous-operational-runtime-consolidation.md` e `docs/ci/AUTONOMOUS_OPERATIONAL_RUNTIME.md`.
- Diretriz transversal de padrão ouro em `docs/REQSYS_PADRAO_OURO_TRANSVERSAL.md`.
- Varredura técnica inicial em `docs/varreduras/REQSYS_VARREDURA_PADRAO_OURO_2026-06-20.md`.
- Helper puro `frontend/src/utils/filtrosRequisitos.js` para normalização, query string e filtragem analítica de requisitos.
- Helper puro `frontend/src/utils/filtrosIntegracao.js` para drill-down analítico do Painel de Integrações (origem, status, data, correlation_id e busca).
- Helpers `filtrosGovbi.js`, `filtrosPipeline.js` e `filtrosTaskConsole.js` com testes unitários para drill-down analítico; GovBI inclui `calcularMetricasGovbi` e `exportarEvidenciaGovbi`.
- Constante `frontend/src/constants/rotasResponsivas.js` com as 16 rotas operacionais canônicas para validação responsiva.
- Helper E2E `tests/e2e/helpers/responsiveMocks.js` para mocks estáveis das 16 rotas.
- Teste unitário `frontend/src/utils/filtrosIntegracao.test.js` para filtros analíticos de integrações.
- Teste unitário `frontend/src/utils/filtrosRequisitos.test.js` para filtros analíticos de requisitos.
- Script `npm run test:unit` no frontend.
- Painel runtime de Connection Broker em `frontend/src/views/MonitoramentoOperacionalView.vue`, com cards, analítico, fallback seguro e consumo futuro de `/api/connectors/health`.
- Contrato técnico dos endpoints `/api/connectors/health` e `/api/connectors/capabilities/check` em `docs/api/connection-broker-runtime-contract.md`.
- Backend .NET inicial do Connection Broker com `GET /api/connectors/health`, `POST /api/connectors/capabilities/check` e aliases versionados em `/v1/connectors/*`.
- Testes xUnit cobrindo shape do health-check e bloqueio governado de escrita em produção.
- Registry em memória do Connection Broker no `ReqSysStore`, com capabilities por ambiente, status, criticidade e necessidade de confirmação humana.
- Auditoria operacional para `connection_broker.capability_check` com `correlation_id` rastreável.
- Teste xUnit validando que a validação de capability registra trilha de auditoria com `correlation_id`.
- Registry persistente versionado em `backend-dotnet/src/ReqSys.Api/config/connectors/connection-broker-registry.json`.
- Carga configurável do registry via variável `REQSYS_CONNECTION_BROKER_REGISTRY`, com fallback governado em memória quando o arquivo não estiver disponível ou for inválido.
- Teste xUnit validando carga do registry JSON e auditoria de carregamento.

### Alterado

- `DashboardView.vue`: cards de requisitos agora apontam para rotas analíticas com filtros por query string quando aplicável.
- `DashboardView.vue`: card de erros de integração com drill-down para `/painel-integracao?status=erro`.
- `DashboardView.vue`: melhoria de acessibilidade por teclado nos cards interativos.
- `PainelIntegracaoView.vue`: analítico filtrável por origem, status, data, correlation_id e busca textual, com cards clicáveis e sincronização de query string.
- `GovBIView.vue`: histórico analítico padrão ouro com métricas clicáveis (total, sucesso, degradado, latência média), filtro de fallback, exportação de evidência JSON, `filter-grid`/`responsive-table-shell`, query string e **painel permanente de funcionamento** com testes locais + API exibidos sempre na tela.
- `govbiFuncionamento.js` e endpoint `GET /api/govbi/funcionamento` para auto-teste com percentual 100%.
- `PipelineView.vue`: histórico de execuções com analítico por etapa, duração, status e correlation_id.
- `TaskConsoleView.vue`: filtros analíticos de tarefas e histórico de envios ao Planner com query string.
- `DashboardView.vue`: cards de drill-down para GovBI degradado, pipeline com erro e Task Console pendente.
- `styles.css`: utilitários responsivos globais (`.page-actions`, `.filter-grid`, shells de tabela) para Hub, GovBI, Task Console e demais telas.
- `data-testid` nas 16 rotas operacionais para validação E2E de responsividade.
- `tests/e2e/responsividade.spec.js`: cobertura das 16 rotas em mobile, tablet e desktop sem overflow horizontal.
- `MonitoramentoOperacionalView.vue`: expansão para incluir indicadores de conectores, criticidade, ações sugeridas e `correlation_id`.
- `ReqSysEndpoints.cs`: módulo `connection-broker` passa a constar em `/v1/sistema/info`.
- `ReqSysEndpoints.cs`: endpoints do Connection Broker deixam de usar payload estático local e passam a consumir o registry do `ReqSysStore`.
- `ReqSys.Api.csproj`: registry JSON passa a ser copiado para o output da aplicação.

### Pendente

- A atualização completa de `RequisitosView.vue` para consumir os filtros por query string foi bloqueada pelo conector de escrita durante este ciclo. Deve ser tratada em PR técnico específico, mantendo a lógica já isolada em `filtrosRequisitos.js`.
- Evoluir o Connection Broker para health-check real por provedor e exportação de métricas.
- Persistir auditoria em storage durável externo ao processo.

### Ambiente

- Ambiente observado: GitHub / branch `main`.
- Ambiente de aplicação: branch `feature/connection-broker-registry-file`.
- Produção: sem alteração direta.

---

## [3.1.0] - 2026-05-28

### Adicionado

- REQSYS#323: Ops Dashboard com drill-down por domínio, detalhes de health/evidence/risk/environment drift/governance, Incident Timeline local filtrável e integração opcional de `runtime-health-report.json` e `runtime-operational-evidence-graph.json`.
- Versionamento canônico em `VERSION` antes do desenvolvimento da nova aplicação.
- Documentação GitFlow em `docs/GITFLOW.md`, com branches, checklist de release, convenção de commits e fluxo de tag.
- Aplicação inicial completa em .NET 8/C# em `backend-dotnet/`, com solution, projeto ASP.NET Core Minimal API, Dockerfile, README e testes xUnit.
- Módulos .NET entregues: autenticação, saúde, sistema, dashboard, requisitos CRUD, pipeline, relatórios, auditoria e qualidade IA.

### Alterado

- README atualizado para declarar a versão `3.1.0` e a nova stack .NET/C# em evolução.
- API FastAPI existente alinhada para versão `3.1.0` e compatibilidade dos testes de autenticação/diagnóstico de segredos.
- Metadados de versão dos assemblies .NET centralizados em `backend-dotnet/Directory.Build.props`.
- `.gitignore` atualizado para ignorar banco local de testes na raiz e permitir rastrear a solution .NET em `backend-dotnet/`.

### Testado

- Conferência estática dos artefatos C# criados e dos arquivos de versionamento.
- Teste automatizado .NET documentado em `backend-dotnet/tests/ReqSys.Api.Tests`; execução local bloqueada no ambiente atual porque o SDK `dotnet` não está instalado.

### Rollback

- Remover o diretório `backend-dotnet/`, reverter `VERSION`, `README.md`, `CHANGELOG.md` e `docs/GITFLOW.md` para retornar ao backend FastAPI como única implementação ativa.

---

## [2.8.0] - 2026-05-15

### Adicionado

- REQSYS#323: Ops Dashboard com drill-down por domínio, detalhes de health/evidence/risk/environment drift/governance, Incident Timeline local filtrável e integração opcional de `runtime-health-report.json` e `runtime-operational-evidence-graph.json`.
- **Integração completa com Redmine Wiki Sync service**
  - ReqSys agora publica documentação de requisitos nas páginas Wiki do Redmine via serviço dedicado (`redmine-wiki-sync-enterprise-v9`) com fila RabbitMQ e worker assíncrono
  - `POST /v1/wiki/requisitos/{id}/publicar` — publica um requisito na Wiki
  - `GET  /v1/wiki/requisitos/{id}/status` — consulta status de sincronização
  - `POST /v1/wiki/requisitos/publicar-lote` — publica todos os requisitos em lote

- **Verificação de versão no GitHub antes de publicar**
  - Antes de qualquer publicação, o ReqSys consulta o GitHub para verificar se já existe uma versão do arquivo
  - Se conteúdo for **idêntico** → publicação ignorada (evita sobrescrita desnecessária)
  - Se conteúdo for **divergente** → publicação bloqueada com alerta; use `forcar_atualizacao=true` para forçar
  - Se arquivo **não encontrado** → publicação prossegue normalmente criando a página
  - Status retornados: `sincronizado`, `divergente`, `nao_encontrado`, `verificacao_desabilitada`, `erro`

- **Gate de pré-validação operacional** (`POST /v1/processos/pre-validar`, `POST /v1/processos/iniciar`)
  - Valida campos obrigatórios, RBAC por escopo, evidências, regras por tipo e score de prontidão (0–100)
  - Tipos suportados: `demanda`, `servico`, `dossie`

- **RBAC expandido**: escopos `demanda:iniciar/cancelar/aprovar/arquivar`, `servico:executar/cancelar/aprovar`, `dossie:criar/iniciar/aprovar/arquivar` e novo perfil `gestor`

- **Novos arquivos**:
  - `app/services/wiki_publisher.py` — orquestra geração de conteúdo Markdown, verificação GitHub e chamada ao Wiki Sync
  - `app/services/github_version_checker.py` — verifica e compara versão de arquivos no GitHub via API REST
  - `app/schemas/wiki.py` — modelos `PublicarWikiRequest`, `PublicarWikiResult`, `GitHubVersionStatus`, `WikiStatusResult`
  - `app/schemas/processos.py` — modelos `ContextoAntecipacao`, `ResultadoAntecipacao`, `ItemValidacao`, `TipoProcesso`, `Severidade`
  - `app/services/prontidao.py` — lógica de `antecipar_validacoes()` e funções de validação por tipo
  - `app/api/wiki.py` — router `/v1/wiki`
  - `app/api/processos.py` — router `/v1/processos`

### Alterado

- Versão da API: `2.6.0` → `2.8.0`
- `app/core/config.py`: novas variáveis `WIKI_SYNC_BASE_URL`, `WIKI_SYNC_TOKEN`, `GITHUB_DOCS_REPO`, `GITHUB_DOCS_BASE_PATH`, `app_version`

---

## Runtime Health Center + Operational Status Aggregator

- Adicionado agregador local `scripts/runtime_health_center.py` para consolidar status operacional por domínio (`ci_cd`, `evidence_gate`, `governance`, `runtime_risk`, `living_architecture`, `environment`, `remediation`).
- Adicionado workflow `Runtime Health Center` para gerar e publicar o artifact `runtime-health-report.json` sem rede externa, secrets ou deploy.
- Documentado o incremento no Runtime Ops Governance P1, incluindo status do padrão ouro, e adicionados testes unitários do contrato do relatório.
