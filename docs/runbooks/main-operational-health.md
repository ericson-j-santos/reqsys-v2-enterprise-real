# Main Operational Health

## Objetivo

Criar uma verificacao continua e governada da saude operacional da branch `main`, sem deploy e sem alteracao de producao.

## Gatilhos

- `workflow_dispatch` manual.
- Agenda em dias uteis: `17 9 * * 1-5`.

## Escopo validado

O workflow valida:

- existencia do `Main Smoke CI`;
- existencia do `PR Scope Labeler`;
- existencia do `PR CI Watch`;
- existencia do `Fast CI - Operational Guardrails`;
- existencia do script e teste do watcher;
- `PR Scope Labeler` em modo read-only;
- `Main Smoke CI` com artifact de evidencia;
- guardrail `--exclude-run-id` no PR CI Watch;
- sintaxe Python do watcher;
- testes rapidos do watcher.

## Fora de escopo

Este workflow nao:

- executa deploy;
- altera producao;
- altera secrets;
- cria release;
- aplica remediacao automatica;
- faz merge automatico;
- altera labels de PR.

## Artifact de evidencia

Artifact esperado:

`main-operational-health-evidence`

Conteudo:

- `summary.md`
- `evidence.json`

## Relatorio operacional

| Dimensao | Status esperado | Evidencia | Acao se falhar |
|---|---|---|---|
| Workflows criticos | Presentes | `test -f` nos YAMLs | Recriar/corrigir workflow ausente |
| Labeler | Read-only | `grep -qi read-only` | Bloquear novos PRs ate corrigir |
| Smoke pos-merge | Presente | `main-smoke-ci-evidence` no YAML | Corrigir Main Smoke CI |
| PR CI Watch | Guardrail ativo | `--exclude-run-id` | Corrigir watcher antes de novos merges |
| Python watcher | Sintaxe valida | `py_compile` | Corrigir script |
| Testes watcher | Verdes | `pytest` | Corrigir regressao |
| Producao | Inalterada | `deploy=false` | Interromper esteira se houver mutacao |

## Decisao operacional

- Verde: main possui evidencias minimas de saude operacional.
- Vermelho: pausar novos incrementos e corrigir causa raiz.
- Sem artifact: tratar como lacuna de auditoria.

## Guard rail permanente

Qualquer alteracao em workflows de PR deve ser feita em PR isolado, especialmente quando envolver `pull_request_target`.

## Links relacionados

- PR #134: correcao do `PR Scope Labeler` para read-only.
- PR #135: criacao do `Main Smoke CI`.
