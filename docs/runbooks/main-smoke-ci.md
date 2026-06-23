# Main Smoke CI

## Objetivo

Garantir evidência mínima e rápida de saúde da `main` após merges, sem executar deploy e sem alterar produção.

## Motivação

O PR #131 estabilizou o `PR CI Watch`, mas a validação pós-merge não tinha um workflow explícito em `push` para `main`. Este smoke check cria um sinal operacional objetivo para confirmar que a branch principal continua validável depois da integração.

## Gatilhos

- `push` na branch `main`.
- `workflow_dispatch` manual.

## Escopo validado

O workflow valida:

- presença de `.github/workflows/pr-ci-watch.yml`;
- presença de `.github/workflows/ci-fast-operational.yml`;
- presença de `scripts/pr_ci_watch.py`;
- presença de `tests/test_pr_ci_watch.py`;
- presença de `docs/runbooks/pr-ci-watch.md`;
- uso de `--exclude-run-id` no PR CI Watch;
- uso de artifact no PR CI Watch;
- presença do workflow `Fast CI - Operational Guardrails`;
- sintaxe Python do watcher;
- testes rápidos do watcher.

## Fora de escopo

Este workflow não:

- executa deploy;
- altera produção;
- cria release;
- altera secrets;
- aplica remediação automática;
- faz merge automático.

## Artifact de evidência

O artifact `main-smoke-ci-evidence` contém:

- `summary.md` com o escopo da validação;
- `evidence.json` com branch, SHA, run id e flags explícitas de não deploy/não alteração de ambiente.

## Decisão operacional

- Verde: `main` tem evidência mínima pós-merge.
- Vermelho: bloquear próximo incremento até capturar log e corrigir a causa raiz.
- Ausência de run em `main`: tratar como lacuna de evidência operacional.

## Relação com PR CI Watch

O `Main Smoke CI` não substitui o `PR CI Watch`. Ele complementa a esteira:

1. PR valida antes do merge.
2. Merge integra na `main`.
3. Main Smoke CI gera evidência pós-merge.

## Risco reduzido

- Merge sem sinal pós-integração.
- Falso conforto por checks apenas no PR.
- Falta de artifact rastreável para a `main`.
