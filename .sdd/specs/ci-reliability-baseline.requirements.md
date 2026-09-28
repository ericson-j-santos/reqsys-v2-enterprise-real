# Requisitos — Baseline observacional de confiabilidade do CI

## Objetivo

Consumir no ReqSys o contrato de evidência criado no Engineering Control Plane sem duplicar um novo gate bloqueante. A coleta deve enriquecer o artifact existente do `CI Lead Time Analytics` com evidência real de flakiness, divergência de SHA e pickup de runner.

## Requisitos funcionais

1. A coleta deve permanecer `report-only` e declarar `creates_gate=false`.
2. A amostra deve reutilizar os PRs já selecionados em `pr_efficiency`, evitando uma segunda varredura global de histórico.
3. Para cada PR amostrado, comparar `latest_head_sha` observado com o `head.sha` atual do PR e registrar `SHA_DIVERGENT` quando forem diferentes.
4. Para cada workflow bloqueante observado no HEAD amostrado, consultar todas as tentativas do mesmo `run_id`; conclusões terminais divergentes devem registrar `FLAKY_UNRESOLVED`.
5. Pickup só é comprovado quando a API de jobs mostra ao menos um job iniciado com `runner_name` não vazio. Ausência dessa prova deve registrar `PICKUP_UNPROVEN`.
6. Coleta incompleta de tentativas ou jobs deve falhar explicitamente; não pode produzir summary verde com evidência parcial silenciosa.
7. O artifact deve registrar contadores agregados, detalhes por PR/run, `head_sha`, `expected_head_sha`, `run_id`, `run_attempt`, conclusões das tentativas, runner e códigos de finding.
8. Reexecutar o enriquecimento sobre o mesmo artifact deve substituir a seção anterior sem duplicar conteúdo.
9. O incremento não altera branch protection, deploy, produção, secrets, permissões administrativas nem required checks.
10. O contrato canônico do gate permanece no Engineering Control Plane; este incremento é apenas consumidor de baseline no ReqSys.

## Critérios de aceite

- teste positivo com duas tentativas `failure -> success` produz `FLAKY_UNRESOLVED`;
- teste negativo com `latest_head_sha != head.sha` produz `SHA_DIVERGENT`;
- teste negativo sem runner atribuído produz `PICKUP_UNPROVEN`;
- coleta incompleta de jobs falha fechado;
- enriquecimento é idempotente;
- `CI Lead Time Analytics` executa o novo enriquecimento e publica o mesmo artifact `audit/ci-lead-time-analytics.json`;
- Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato antes da abertura da PR.

## Evidência

Registrar branch, HEAD SHA, base SHA, run do Pre-PR Readiness, run do CI Lead Time Analytics quando materializado, artifact gerado e os três contadores observacionais.

## Rollback

Reverter somente os arquivos deste incremento. Como a coleta é report-only e não cria gate, o rollback não altera regras de merge nem runtime.
