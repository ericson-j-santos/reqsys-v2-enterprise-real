# Avaliação das integrações ReqSys — DEV — 01/10/2026

Base inspecionada: `13b0b267c15fc0d2f750ccaa649b761c866e2937`, repositório
`ericson-j-santos/reqsys-v2-enterprise-real`. Ambiente solicitado: DEV.

## Conclusão

As quatro capacidades possuem código. A reconsulta de GitHub Actions confirmou
prova real verde de Planner → Teams no run `36899070559`, SHA `13b0b267...`,
em 01/10/2026. A publicação ReqSys → Planner e o gateway ReqSys → Teams no PC24x7
continuam com aceite específico pendente, assim como Redmine e sua sincronização.
Execução e pendências atualizadas: [TODO de aplicação](todo-integracoes-dev.md).

| Capacidade | Evidência | Ação necessária |
|---|---|---|
| Redmine: leitura/criação de issues | Adaptadores e testes presentes; nenhuma instância autenticada acessível nesta sessão | Provisionar URL, API key, projeto e versão confirmada; testar usuário/projeto e criação com leitura independente |
| Sincronização Redmine | Fila Dataverse e lifecycle individual/lote implementados; issue #1686 exige E2E real | Validar schema Dataverse, Application User, vínculo requisito/issue; executar ida/volta, replay e falha; só então ativar recorrência |
| Planner | Publicação governada/idempotência/reprocessamento implementados; issue #32 exige aceite real | Configurar webhook/conexão/plano/bucket; publicar e confirmar tarefa no Planner; repetir sem duplicidade; testar falha/reprocessamento |
| Teams | Planner → Teams com prova real verde, leitura Graph disponível e controles positivos/negativos; gateway PC24x7 pendente em #729 | Validar caminho ReqSys → Teams e vínculo ao SHA publicado; não conceder permissões por bloqueio histórico já superado |

Planner possui publicação governada; isso não comprova sincronização bidirecional
completa. O ciclo de resposta/anexo Teams → ReqSys/Planner é acompanhado em #1509.

## Verificações realizadas

- 87 testes backend selecionados: **passaram**, cobrindo Redmine API/fila/lifecycle/lote,
  Planner publicação/API e Teams gateway/Planner-notificação. Usam mocks e banco de
  testes isolado; não comprovam entrega externa.
- 9 testes de script e resolução de alvo do reprocessamento: **passaram**.
- 14 testes de API Planner após a correção: **passaram**, incluindo token real
  com escopo correto, rejeição de escopo errado e rejeição sem credenciais.
- Locator público DEV consultado e validado pelo resolver canônico:
  `no_valid_fresh_signed_locator`. Isso indica ausência de endereço fresco assinado
  aceitável nesta consulta; não prova que o host está desligado.
- Ambiente desta sessão: nenhuma identidade externa, segredo ou variável de
  integração provisionados. `configurar_redmine_sync_queue.py status` apontou
  ausência das oito variáveis exigidas **nesta sessão**, sem acesso ao cofre do host.
- URLs Fly DEV/STG/PROD responderam health 200, mas são legadas desde 11/09/2026
  (`docs/DEPRECATIONS.md`); não servem para homologar PC24x7.
- Gateway Fly DEV informou webhook/bot disponíveis e Flow bot não configurado.
  Essa observação pertence somente ao runtime legado, não ao PC24x7 DEV.
- Certificação pública GitHub → Teams respondeu `quality_blocked`, entregas
  98,68% em 379 runs e monitor 38,84% em 121 runs. Artifact vinculado ao run
  `36622607533`; a janela ainda aponta 29,79 dias, por isso não é evidência nova
  de entrega em 01/10. Também não comprova o fluxo ReqSys/Planner → Teams.

## Correção preparada no código local

O workflow `planner-publish-reprocess-scheduled.yml` ainda direcionava chamadas
para Fly.io. Agora usa `vars.REQSYS_API_BASE_URL` do GitHub Environment selecionado,
exige HTTPS, recusa Fly.io/credenciais/query na URL e falha quando o token está
ausente. Passa `--strict` para sinalizar respostas HTTP inesperadas.

Limitação: `--strict` detecta HTTP inesperado; uma tentativa que retorna HTTP 200
com `falhou_integracao` permanece registrada como `ainda_falhando` na evidência.

O ajuste foi testado localmente. A execução da publicação em PR e os bloqueios
restantes estão registrados no TODO. Não houve deploy, mudança de segredo,
consentimento ou envio de mensagem externa nesta sessão.

Foi corrigida também a incompatibilidade de autenticação do agendador: o script
enviava `X-Service-Token` para a listagem `/planner/publish`, que exige JWT.
O novo `GET /v1/hub-lowcode/planner/reprocessamento/pendentes` aceita admin ou
token com `planner_publish:enviar` e lista apenas `falhou_integracao`. A listagem
da tela continua usando sua rota existente. Backend e script devem ser publicados
juntos antes de executar o workflow atualizado.

## Sequência de aplicação em DEV

1. Restabelecer o locator assinado ou disponibilizar o endereço canônico PC24x7
   DEV. Conferir `/api/health` e `/api/runtime/build-info`, registrando o SHA do
   runtime. Não usar Fly como fallback.
2. Pelo cofre do host DEV, provisionar `REDMINE_BASE_URL`, `REDMINE_API_KEY`,
   `REDMINE_PROJECT_ID`, `REDMINE_VERSION`, `REDMINE_SYNC_DATAVERSE_URL`,
   `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`.
   Configurar Application User Dataverse e permissões às tabelas do fluxo.
3. Executar no contexto DEV configurado:
   `python scripts/configurar_redmine_sync_queue.py verificar`.
   O comando faz preflight de leitura por padrão; não criar issue de teste antes
   de selecionar projeto e requisito DEV de teste.
4. Validar `cr85a_redminequeue`, `cr85a_agilesync` e `cr85a_auditlog` pelos metadados
   reais. Garantir `cr85a_reservedat`, `cr85a_retrycount`, `cr85a_errordetail` e
   `cr85a_correlationid` textual com pelo menos 36 caracteres (100 recomendado).
   Ajustar apenas gaps confirmados; o documento histórico não comprova ausência
   atual das colunas.
5. Executar fila em `dry_run`; depois testar criação real e reconciliação
   título/descrição → Redmine e status/responsável/progresso/journals → snapshot
   ReqSys. Repetir sem alterações e exigir zero mutações adicionais. Confirmar
   falha, backoff e quarentena antes de ativar recorrência (#1686).
6. Configurar `POWERAUTOMATE_PLANNER_WEBHOOK_URL`/chave ou a configuração
   persistida em `/v1/hub-lowcode/planner/webhook-config`, conexão Microsoft,
   plano e bucket DEV. Usar `/v1/hub-lowcode/planner/publish`, conferir tarefa
   por leitura independente, `planner_task_id`, replay e reprocessamento (#32).
7. Após revisar/publicar o ajuste local, configurar **no Environment development**
   a variável `REQSYS_API_BASE_URL` para a base API PC24x7 DEV (com `/api` se esse
   prefixo for exigido pelo gateway) e o secret `PLANNER_PUBLISH_SERVICE_TOKEN`
   com escopo `planner_publish:enviar`. Validar manualmente o workflow antes de confiar
   na recorrência de 30 minutos. Não aplicar a staging neste aceite DEV.
8. Escolher o canal Teams usado pelo fluxo. Webhook exige URL/conexão válidas;
   bot exige identidade configurada, instalação e conversationReference;
   Flow bot exige URL ou dono ativo. Não é necessário ativar todos os canais.
9. Preservar as permissões atuais: o artifact do run `36899070559` confirma leitura
   Graph disponível e Planner → Teams verde. Revalidar o caminho que parte do
   ReqSys após a publicação, sem conceder permissões com base no 403 histórico.
10. Registrar ambiente, SHA, run/artifact, `correlation_id` e IDs externos da
    mesma execução. Concluir homologação do gateway (#729) com entrega observada,
    controle negativo, rastreabilidade e ausência de duplicidade.

## Risco e rollback do ajuste

O agendamento passa a ficar vermelho se a URL/token não estiverem configurados.
Isso expõe um bloqueio antes ocultado por sucesso sem execução. Manter o workflow
desativado enquanto DEV não estiver homologado é uma opção operacional; não
voltar a apontá-lo ao Fly. Reverter o diff local restaura o comportamento anterior,
mas também restaura o alvo legado e o falso sucesso quando falta token.

## Referências

- https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1686
- https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/32
- https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/729
- https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1644
- https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1509
- `docs/architecture/redmine-sync-queue.md`
- `docs/architecture/redmine-lifecycle-sync.md`
