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

## Relatório de Monitoramento do PR

| Dimensão | Status | Evidência | Risco | Ação recomendada |
|---|---|---|---|---|
| Escopo alterado | Controlado | Novo workflow `main-smoke-ci.yml` e este runbook | Baixo | Manter mudança pequena e rastreável |
| Build/CI | Validável no head do PR | Checks principais do PR devem estar verdes antes do merge | Médio | Bloquear merge se houver falha, cancelamento ou pendência |
| Testes | Coberto por smoke rápido | `python -m pytest tests/test_pr_ci_watch.py -q` | Baixo | Reexecutar em caso de falha e capturar log |
| Segurança | Sem alteração produtiva | `contents: read`, sem secrets e sem deploy | Baixo | Não adicionar permissões elevadas |
| Observabilidade | Artifact operacional | `main-smoke-ci-evidence` com `summary.md` e `evidence.json` | Baixo | Validar artifact após execução em `main` |
| Documentação | Atualizada | Runbook com escopo, decisão operacional e tabelas | Baixo | Manter este documento sincronizado com o workflow |
| Ambiente | Main pós-merge | Gatilho em `push` para `main` | Médio | Usar apenas como evidência pós-merge, não como aprovação de deploy |
| Auditoria | Rastreável | SHA, branch, run id e flags de não deploy no JSON | Baixo | Preservar retenção do artifact |

## Resultado da Revisão

| Critério | Resultado | Bloqueia merge? | Observação |
|---|---|---|---|
| Compilação YAML | Aprovado quando GitHub Actions aceitar o workflow | Sim, se falhar | Validar no head do PR |
| Testes automatizados | Aprovado quando `tests/test_pr_ci_watch.py` passar | Sim, se falhar | Executado no próprio workflow |
| Segurança mínima | Aprovado | Não | Permissão mínima `contents: read`; sem secrets, deploy ou produção |
| Governança/ADR | Aprovado | Não | Incremento operacional pós-PR #131; sem mudança arquitetural de negócio |
| Documentação | Aprovado | Não | Runbook contém escopo, tabelas, decisão operacional e evidência |
| Pronto para revisão humana | Condicional | Sim | Só considerar pronto se CI completo do head estiver verde |

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
