# TODO de aplicação — integrações ReqSys DEV

Atualizado em 01/10/2026. Escopo: PC24x7 DEV e Power Platform DEV.
`[x]` significa executado/comprovado; `[ ]` significa pendente. Bloqueio não
é conclusão. Não promover HML/PROD por este TODO.

## 1. Correções do reprocessamento Planner — execução nesta frente

- [x] Retirar URLs Fly.io fixas do workflow e exigir base API PC24x7 HTTPS.
- [x] Sinalizar falta de token como falha, em vez de sucesso sem execução.
- [x] Criar listagem de pendências compatível com token de serviço escopado:
  `GET /v1/hub-lowcode/planner/reprocessamento/pendentes`.
- [x] Atualizar o script para consumir a rota S2S, preservando a listagem JWT da tela.
- [x] Executar 14 testes da API Planner, incluindo token real com escopo correto,
  escopo errado e ausência de credencial; 9 testes de script/alvo do workflow.
- [x] Executar gates individuais de produção, CORS e JWT: 15 testes passaram.
- [x] Revalidar as integrações na base atualizada `ee6870a...`: 90 testes backend
  passaram, além dos 9 testes de script/workflow.
- [x] Executar o gate de incremento como hotfix de escopo fechado da issue #32:
  decisão `allowed=true` com o artifact local de coordenador versionado.
- [x] Publicar a correção em [PR #2185](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/2185),
  com base atualizada e testes locais verdes.
- [ ] Aguardar CI completo, revisão e merge governados da PR #2185.
- [ ] Publicar backend e script juntos em PC24x7 DEV; confirmar `build-info` no SHA
  do merge antes de disparar reprocessamento.

## 2. Acesso ao runtime e configuração — bloqueios atuais

- [x] Reconsultar locator público usando verificação de assinatura/validade canônica.
- [ ] Restabelecer locator fresco no host PC24x7 DEV: consulta desta sessão retornou
  `no_valid_fresh_signed_locator`. Owner do host deve verificar supervisor Windows
  `ReqSys-Dev-Runtime-Supervisor`, tunnel e publicação do locator; usar componentes
  existentes `pc24x7_dev_runtime_supervisor.py` e `pc24x7_dev_locator_publisher.py`.
- [ ] Confirmar `/api/health`, `/api/runtime/health` e `/api/runtime/build-info` e SHA
  exato do runtime acessível.
- [ ] Disponibilizar acesso ao cofre/host DEV no ambiente de execução. Nesta sessão,
  `environment_status` confirma zero segredos, variáveis e identidades externas.
- [ ] Resolver acesso às configurações do GitHub Environment `development`.
  Listagem de nomes de variables/secrets retornou HTTP 403; os valores não foram lidos.
- [ ] Configurar `REQSYS_API_BASE_URL` no Environment `development` para a base API
  PC24x7 DEV; incluir `/api` quando o gateway exigir esse prefixo.
- [ ] Configurar `PLANNER_PUBLISH_SERVICE_TOKEN` com escopo `planner_publish:enviar`.
  Gerar pelo mecanismo autenticado existente; não inserir valores no TODO/PR/log.

## 3. Redmine — configuração e prova real

- [ ] Confirmar presença no cofre DEV de `REDMINE_BASE_URL`, `REDMINE_API_KEY`,
  `REDMINE_PROJECT_ID`, `REDMINE_VERSION`. Ausência nesta sessão não comprova ausência
  no host; último bloqueio operacional documentado: issue #1686.
- [ ] Executar `python scripts/configurar_redmine_sync_queue.py verificar` no contexto
  DEV configurado; esse preflight verifica leitura e versão sem criar issue por padrão.
- [ ] Confirmar usuário/projeto e API REST ativa; corrigir acesso somente se o
  preflight identificar falha real.
- [ ] Criar uma issue DEV de teste, confirmar por leitura independente e registrar
  issue ID, requisito ID, SHA e `correlation_id`.

## 4. Sincronização com Redmine — fila e lifecycle

- [ ] Configurar `REDMINE_SYNC_DATAVERSE_URL` e identidade Dataverse autorizada.
  Validar a configuração de identidade vigente, incluindo o cutover Microsoft
  em PR #2183; não copiar defaults/segredos de outro ambiente.
- [ ] Verificar Application User e permissões em `cr85a_redminequeue`,
  `cr85a_agilesync` e `cr85a_auditlog`.
- [ ] Confirmar schema real: reserva, contagem de tentativas, detalhe de erro e
  correlation ID textual com comprimento mínimo 36 (100 recomendado).
- [ ] Executar fila em `dry_run`, depois criação real com retorno de issue ID.
- [ ] Validar título/descrição ReqSys → Redmine e status/responsável/progresso/
  journals Redmine → snapshot ReqSys, respeitando propriedade de campos.
- [ ] Repetir sem alterações: zero mutações adicionais e nenhum journal duplicado.
- [ ] Validar falha externa, backoff/quarentena e recuperação sem duplicidade.
- [ ] Registrar evidência no mesmo SHA e então ativar recorrência governada (#1686).

## 5. ReqSys → Planner — publicação governada

- [ ] Confirmar webhook/configuração persistida, conexão Microsoft, plano e bucket DEV.
- [ ] Usar `POST /v1/hub-lowcode/planner/publish` para publicar uma tarefa de teste.
- [ ] Confirmar a tarefa diretamente no Planner e registrar `planner_task_id`,
  `attempt_id`, chave idempotente e `correlation_id`.
- [ ] Repetir exatamente a entrada e comprovar ausência de segunda tarefa.
- [ ] Simular falha controlada e comprovar registro/reprocessamento sem duplicidade.
- [ ] Executar manualmente `Planner Publish — Reprocessamento Automático` após
  merge/publicação/configuração; verificar artifact e cada desfecho de negócio.
- [ ] Somente após prova real verde, aceitar a recorrência de 30 minutos (#32).

## 6. Planner → Teams — evidência real já disponível

- [x] Consultar e ler artifact real de `Runtime E2E Continuous — DEV`, run
  [36899070559](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/36899070559).
- [x] Confirmar `status=passed`, OIDC, `mocked=false`, `simulated=false`,
  `tokens_persisted=false` e SHA `13b0b267c15fc0d2f750ccaa649b761c866e2937`.
- [x] Confirmar leitura Graph disponível, exatamente uma mensagem da tarefa normal,
  zero mensagens `REQSYS-E2E-*` e ambas as tarefas apagadas no cleanup.
- [x] Confirmar Adaptive Card com Progresso/Vencimento e link para a tarefa correta.
- [x] Confirmar os dois flows de criação/conclusão ativos, com connection references
  Planner/Teams; nenhum patch do cartão foi necessário nesse run.
- [ ] Validar o caminho governado **ReqSys → Planner → Teams** após publicar a
  correção. O run acima cria tarefas diretamente pelo Graph, portanto não comprova
  a rota de publicação do ReqSys nem o seu reprocessamento.

O HTTP 403 registrado historicamente em #1644 não se reproduz nessa evidência:
não conceder permissões adicionais por esse diagnóstico antigo. A prova de criação
está verde; o run não afirma ter exercitado uma notificação de conclusão de tarefa.

## 7. ReqSys → Teams Gateway — homologação separada

- [ ] Consultar `/api/v1/teams-gateway/status` no PC24x7 DEV acessível e escolher
  um canal efetivamente configurado para o destinatário DEV.
- [ ] Verificar `dry_run` sem envio, depois mensagem de teste real com confirmação
  independente no Teams, rastreabilidade e replay seguro (#729).
- [ ] Validar caso negativo de rota/configuração ausente, sem falso sucesso de entrega.
- [ ] Anexar logs/evidências sanitizados no mesmo SHA e atualizar a homologação.

## Critério de término

Concluir o TODO somente quando correções estiverem publicadas e as provas reais
de Redmine, sincronização, ReqSys → Planner e ReqSys → Teams estiverem verdes no
DEV configurado. CI/mocks e o fluxo direto Graph → Planner → Teams têm alcance
específico e não substituem esses aceites.

Referências: issues #32, #1686, #729; cutover de identidade Microsoft PR #2183.
