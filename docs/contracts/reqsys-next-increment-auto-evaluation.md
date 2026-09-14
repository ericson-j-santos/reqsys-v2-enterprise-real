# ReqSys Next Increment Auto Evaluation

## Objetivo

Avaliar automaticamente, de forma `report-only`, a sequência governada:

1. validar PRs abertas, Merge Queue e workflows obrigatórios;
2. consolidar artefatos instrumentados de readiness e histórico;
3. executar smoke público nos endpoints contratuais do runtime;
4. calcular throughput de integração e lead time de merge;
5. medir o tempo entre merge, CI verde e observação do mesmo SHA no runtime;
6. publicar resumo executivo apenas com métricas instrumentadas;
7. calcular e expor ETA somente quando o histórico tiver evidência suficiente.

## Frequência

- execução horária;
- acionamento manual;
- execução após conclusão do `ReqSys Fly Runtime P0`;
- execução após alteração do contrato na `main`.

## Fontes instrumentadas

- GitHub Pull Requests abertas e mergeadas;
- GitHub Actions e required workflows;
- artifacts `instrumented-executive-readiness` e `instrumented-executive-history`;
- runtime público `https://reqsys-api.fly.dev`:
  - `/health`;
  - `/api/runtime/health`;
  - `/api/runtime/readiness`;
  - `/api/runtime/liveness`;
  - `/api/runtime/build-info`.

## Saídas

- `report.json`: contrato estruturado e auditável, schema `1.2.0`;
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

## Separação de espera

O relatório distingue:

- `merge_to_ci_green_minutes`: trecho técnico até CI principal verde;
- `merge_to_runtime_observed_minutes`: trecho até evidência pública do mesmo SHA;
- `external_blocked_minutes`: permanece `null` enquanto não houver uma fonte confiável para início/fim de bloqueio externo;
- `external_wait_status`: `not_instrumented` enquanto essa fonte não existir.

Isso evita atribuir a dependências externas um tempo estimado ou inventado.

## Alvo operacional

Para DEV e incrementos sem human gate/dependência externa, o alvo inicial é:

- `availability_target_minutes = 30`.

O alvo é report-only: não altera merge, promoção, branch protection ou gates. Mudanças com permissões administrativas, segredos, infraestrutura crítica, dependências de fornecedor ou aprovação humana devem ser reportadas separadamente e não ter o tempo externo ocultado dentro do tempo técnico.

## Estados

- `READY_FOR_HUMAN_DECISION`: gates, runtime e evidências suficientes; decisão humana continua obrigatória;
- `ACTION_REQUIRED`: existe falha, pendência, runtime indisponível, evidência incompleta ou histórico insuficiente.

## Priorização automática

1. `remediate_failed_required_workflows`;
2. `complete_required_workflows`;
3. `restore_runtime_and_smoke_evidence`;
4. `complete_instrumented_evidence`;
5. `accumulate_instrumented_history`;
6. `governed_merge_of_eligible_prs`;
7. `maintain_runtime_and_delivery_baseline`.

## Guardrails

- não realiza merge;
- não habilita auto-merge;
- não promove ambiente;
- não altera branch protection;
- não substitui required checks;
- aprovação humana permanece obrigatória;
- dados ausentes não são estimados;
- disponibilidade não é inferida sem vínculo exato de SHA;
- tempo bloqueado por dependência externa não é fabricado quando não instrumentado.
