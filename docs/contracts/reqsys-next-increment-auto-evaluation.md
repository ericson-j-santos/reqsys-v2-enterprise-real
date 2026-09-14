# ReqSys Next Increment Auto Evaluation

## Objetivo

Avaliar automaticamente, de forma `report-only`, a sequência governada:

1. validar PRs abertas, Merge Queue e workflows obrigatórios;
2. consolidar artefatos instrumentados de readiness e histórico;
3. executar smoke público nos endpoints contratuais do runtime;
4. calcular throughput de integração e lead time de merge;
5. medir o tempo entre merge, CI verde e observação do mesmo SHA no runtime;
6. decompor espera externa somente a partir de eventos estruturados e auditáveis;
7. publicar resumo executivo apenas com métricas instrumentadas;
8. calcular e expor ETA somente quando o histórico tiver evidência suficiente.

## Frequência

- execução horária;
- acionamento manual;
- execução após conclusão do `ReqSys Fly Runtime P0`;
- execução após alteração do contrato na `main`.

## Fontes instrumentadas

- GitHub Pull Requests abertas e mergeadas;
- GitHub Actions e required workflows;
- artifacts `instrumented-executive-readiness` e `instrumented-executive-history`;
- issue ledger GitHub `#1683` para eventos estruturados de espera externa;
- runtime público `https://reqsys-api.fly.dev`:
  - `/health`;
  - `/api/runtime/health`;
  - `/api/runtime/readiness`;
  - `/api/runtime/liveness`;
  - `/api/runtime/build-info`.

## Saídas

- `report.json`: contrato estruturado e auditável, schema `1.3.0` após enriquecimento da partição de espera;
- `report.md`: resumo executivo para o GitHub Step Summary;
- artifact `reqsys-next-increment-auto-evaluation`, retido por 90 dias.

## Indicadores

- estabilidade dos required workflows;
- sucesso e latência média dos smoke checks públicos;
- PRs mergeadas em 24 horas e 7 dias;
- lead time mediano entre criação e merge;
- lead time mediano entre merge e CI principal verde, quando houver evidência do mesmo SHA;
- tempo entre merge e primeira observação do mesmo SHA saudável no runtime;
- tempo entre criação da PR e primeira observação do mesmo SHA saudável no runtime;
- tempo externo fechado por categoria e ocorrência;
- quantidade de bloqueios externos abertos, fechados, inválidos e duplicados;
- aderência ao alvo operacional de 30 minutos para disponibilidade em DEV sem gate externo;
- throughput paralelo das PRs abertas mergeáveis;
- maturidade histórica, tendência e confiança instrumentada;
- ETA proveniente do histórico, sem preenchimento manual.

## Semântica da disponibilidade

A disponibilidade só é associada a um incremento quando:

1. a PR possui `merge_commit_sha`;
2. `/api/runtime/build-info` retorna `build_sha`;
3. `build_sha` é exatamente igual ao `merge_commit_sha`;
4. os endpoints públicos obrigatórios estão saudáveis;
5. a observação possui timestamp da execução corrente.

O tempo `merge_to_runtime_observed_minutes` é um **limite superior** entre o merge e a primeira observação feita por este avaliador. Ele não deve ser tratado como timestamp exato do deploy até existir uma fonte de evento de deploy com vínculo de SHA.

Nenhuma associação aproximada, por horário, versão, branch ou posição na fila é permitida quando o SHA não casar.

## Instrumentação de espera externa

O ledger é a issue GitHub `#1683`. O workflow `ReqSys External Wait Recorder` é a superfície oficial de gravação.

Cada comentário válido contém o marcador:

`<!-- reqsys-external-wait-event:v1 -->`

e um JSON estruturado com:

- `event_id`;
- `wait_id`;
- `action`: `blocked` ou `unblocked`;
- `category`;
- `correlation_id`;
- `sha`, quando aplicável;
- `source_reference`, quando aplicável.

Categorias aceitas:

- `human_gate`;
- `external_provider`;
- `permission_admin`;
- `secret_or_credential`;
- `infrastructure_external`.

O timestamp usado no cálculo é `created_at` do comentário retornado pela API do GitHub, não um horário informado manualmente no payload.

Texto livre, mensagens sem marcador, ausência de execução e diferenças aproximadas entre runs **não** viram tempo bloqueado.

## Idempotência e antifalso positivo

- `event_id` repetido é ignorado e contado como duplicado;
- o mesmo `wait_id + action + correlation_id` com novo `event_id` também não é contado duas vezes;
- `unblocked` sem `blocked` válido vira sequência inválida;
- bloqueio aberto mantém `unblocked_at=null` e `duration_minutes=null`;
- se a coleta da issue falhar, `external_wait_status=collection_failed` e `external_blocked_minutes=null`;
- nenhum erro de coleta é convertido em zero minutos;
- a duração só é calculada para pares `blocked → unblocked` correlacionados e temporalmente válidos.

## Partição do lead time

`delivery_velocity.wait_partition` passa a expor:

- `technical_intervals_instrumented`;
- `external_blocked_minutes`;
- `external_wait_status`;
- `closed_waits`;
- `open_waits`;
- `invalid_event_count`;
- `duplicate_event_count`;
- `by_category`;
- `waits`.

Estados de `external_wait_status`:

- `not_instrumented`: nenhum evento estruturado observado;
- `instrumented`: eventos válidos sem bloqueios abertos ou sequências inválidas;
- `partial`: existe bloqueio aberto ou evento inválido;
- `collection_failed`: não foi possível consultar a fonte GitHub; minutos permanecem `null`.

## Alvo operacional

Para DEV e incrementos sem human gate/dependência externa:

- `availability_target_minutes = 30`.

O alvo é `report-only`: não altera merge, promoção, branch protection ou gates.

## Guardrails

- não realiza merge;
- não habilita auto-merge;
- não promove ambiente;
- não altera branch protection;
- não substitui required checks;
- aprovação humana permanece obrigatória;
- dados ausentes não são estimados;
- disponibilidade não é inferida sem vínculo exato de SHA;
- tempo externo não é inferido de texto livre;
- eventos do ledger não devem conter segredos, tokens ou credenciais.

## Validação pós-merge

A gravação real pelo `workflow_dispatch` do `ReqSys External Wait Recorder` só pode ser comprovada depois que o workflow existir na `main`.

Validação mínima:

1. registrar `blocked` com `correlation_id` único;
2. reencontrar o comentário pela API do GitHub;
3. executar o avaliador e observar bloqueio aberto sem duração fabricada;
4. registrar `unblocked` para o mesmo `wait_id/correlation_id`;
5. executar novamente o avaliador;
6. confirmar duração pela diferença entre `created_at` dos dois comentários;
7. repetir a entrada ou replay dos comentários e confirmar ausência de dupla contagem;
8. usar evento inválido de controle e confirmar que não entra no total.

Até essa validação ocorrer no SHA integrado, o incremento deve permanecer como **parcialmente validado**.
