# Repository Admin Control Plane — P0 Pareto

## Escopo

Este incremento consolida a issue #115 sobre as capacidades já existentes do
ReqSys. Ele não cria um segundo orquestrador de CI.

O P0 adiciona três funções read-only:

1. registry versionado de repositórios administrados;
2. snapshot da branch padrão vinculado ao SHA exato;
3. decisão determinística de PR/CI vinculada ao HEAD atual.

## Endpoints

- `GET /v1/admin/repositories`
- `GET /v1/admin/repositories/{owner}/{repo}/snapshot`
- `GET /v1/admin/repositories/{owner}/{repo}/pull-requests/{pr}/decision`

Todas as rotas exigem `require_admin`.

## Decisões

| Decisão | Significado |
|---|---|
| `fix_ci` | há check concluído com falha |
| `wait_ci` | há check ainda não concluído |
| `investigate_ci` | existe check inconclusivo, inclusive skipped/neutral |
| `no_ci_evidence` | nenhum check foi observado para o HEAD |
| `blocked_conflict` | GitHub reporta conflito |
| `blocked_unexpected_base` | PR aponta para base diferente da policy |
| `wait_draft` | PR ainda é draft |
| `wait_mergeability` | GitHub ainda não calculou mergeabilidade |
| `ready_for_full_gates` | checks observados estão verdes, mas gates completos ainda precisam validar |

## Guardrails

`ready_for_full_gates` não significa `READY_FOR_MERGE`. O P0 não executa
retry, alteração de branch, merge, deploy, promoção, secrets ou branch
protection.

Toda evidência operacional pertence ao triplo:

`repository + pull_request + head_sha`.

Novo SHA invalida a decisão anterior.
