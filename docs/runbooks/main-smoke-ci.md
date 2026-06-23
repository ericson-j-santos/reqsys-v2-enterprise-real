# Main Smoke CI

## Objetivo

Garantir evidencia minima e rapida de saude da `main` apos merges, sem executar deploy e sem alterar producao.

## Checklist Governanca

- [x] Escopo pequeno, rastreavel e limitado a CI/documentacao.
- [x] Sem deploy.
- [x] Sem alteracao de producao.
- [x] Sem alteracao de secrets.
- [x] Sem merge automatico.
- [x] Sem aumento de permissoes alem de `contents: read`.
- [x] Artifact operacional publicado para auditoria.
- [x] Runbook atualizado com relatorio operacional e resultado da revisao.
- [x] CI do head deve estar verde antes de qualquer decisao de merge.

## Motivacao

O PR #131 estabilizou o `PR CI Watch`, mas a validacao pos-merge nao tinha um workflow explicito em `push` para `main`. Este smoke check cria um sinal operacional objetivo para confirmar que a branch principal continua validavel depois da integracao.

## Gatilhos

- `push` na branch `main`.
- `workflow_dispatch` manual.

## Escopo validado

O workflow valida:

- presenca de `.github/workflows/pr-ci-watch.yml`;
- presenca de `.github/workflows/ci-fast-operational.yml`;
- presenca de `scripts/pr_ci_watch.py`;
- presenca de `tests/test_pr_ci_watch.py`;
- presenca de `docs/runbooks/pr-ci-watch.md`;
- uso de `--exclude-run-id` no PR CI Watch;
- uso de artifact no PR CI Watch;
- presenca do workflow `Fast CI - Operational Guardrails`;
- sintaxe Python do watcher;
- testes rapidos do watcher.

## Relatorio de Monitoramento do PR

| Dimensao | Status | Evidencia | Risco | Acao recomendada |
|---|---|---|---|---|
| Escopo alterado | Controlado | Novo workflow `main-smoke-ci.yml` e este runbook | Baixo | Manter mudanca pequena e rastreavel |
| Build/CI | Validavel no head do PR | Checks principais do PR devem estar verdes antes do merge | Medio | Bloquear merge se houver falha, cancelamento ou pendencia |
| Testes | Coberto por smoke rapido | `python -m pytest tests/test_pr_ci_watch.py -q` | Baixo | Reexecutar em caso de falha e capturar log |
| Seguranca | Sem alteracao produtiva | `contents: read`, sem secrets e sem deploy | Baixo | Nao adicionar permissoes elevadas |
| Observabilidade | Artifact operacional | `main-smoke-ci-evidence` com `summary.md` e `evidence.json` | Baixo | Validar artifact apos execucao em `main` |
| Documentacao | Atualizada | Runbook com escopo, decisao operacional e tabelas | Baixo | Manter este documento sincronizado com o workflow |
| Ambiente | Main pos-merge | Gatilho em `push` para `main` | Medio | Usar apenas como evidencia pos-merge, nao como aprovacao de deploy |
| Auditoria | Rastreavel | SHA, branch, run id e flags de nao deploy no JSON | Baixo | Preservar retencao do artifact |

## Resultado da Revisao

| Criterio | Resultado | Bloqueia merge? | Observacao |
|---|---|---|---|
| Compilacao YAML | Aprovado quando GitHub Actions aceitar o workflow | Sim, se falhar | Validar no head do PR |
| Testes automatizados | Aprovado quando `tests/test_pr_ci_watch.py` passar | Sim, se falhar | Executado no proprio workflow |
| Seguranca minima | Aprovado | Nao | Permissao minima `contents: read`; sem secrets, deploy ou producao |
| Governanca/ADR | Aprovado | Nao | Incremento operacional pos-PR #131; sem mudanca arquitetural de negocio |
| Documentacao | Aprovado | Nao | Runbook contem escopo, tabelas, decisao operacional e evidencia |
| Pronto para revisao humana | Condicional | Sim | So considerar pronto se CI completo do head estiver verde |

## Fora de escopo

Este workflow nao:

- executa deploy;
- altera producao;
- cria release;
- altera secrets;
- aplica remediacao automatica;
- faz merge automatico.

## Artifact de evidencia

O artifact `main-smoke-ci-evidence` contem:

- `summary.md` com o escopo da validacao;
- `evidence.json` com branch, SHA, run id e flags explicitas de nao deploy/nao alteracao de ambiente.

## Decisao operacional

- Verde: `main` tem evidencia minima pos-merge.
- Vermelho: bloquear proximo incremento ate capturar log e corrigir a causa raiz.
- Ausencia de run em `main`: tratar como lacuna de evidencia operacional.

## Relacao com PR CI Watch

O `Main Smoke CI` nao substitui o `PR CI Watch`. Ele complementa a esteira:

1. PR valida antes do merge.
2. Merge integra na `main`.
3. Main Smoke CI gera evidencia pos-merge.

## Risco reduzido

- Merge sem sinal pos-integracao.
- Falso conforto por checks apenas no PR.
- Falta de artifact rastreavel para a `main`.
