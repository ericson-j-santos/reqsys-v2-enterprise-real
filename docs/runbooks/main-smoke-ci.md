# Main Smoke CI

## Objetivo

Garantir evidencia minima e rapida de saude da main apos merges, sem executar deploy e sem alterar producao.

## Checklist Governanca

- [x] Escopo pequeno, rastreavel e limitado a CI/documentacao.
- [x] Sem deploy.
- [x] Sem alteracao de producao.
- [x] Sem alteracao de secrets.
- [x] Sem merge automatico.
- [x] Permissoes minimas.
- [x] Artifact operacional publicado para auditoria.
- [x] Runbook atualizado com relatorio operacional e resultado da revisao.
- [x] CI do head deve estar verde antes de qualquer decisao de merge.

## Motivacao

O PR #131 estabilizou o PR CI Watch, mas a validacao pos-merge nao tinha um workflow explicito em push para main. Este smoke check cria um sinal operacional objetivo para confirmar que a branch principal continua validavel depois da integracao.

## Gatilhos

- push na branch main.
- workflow_dispatch manual.

## Escopo validado

O workflow valida:

- presenca de workflows operacionais;
- presenca de script, teste e runbook do watcher;
- uso de guardrail de exclusao de run;
- uso de artifact no PR CI Watch;
- sintaxe Python do watcher (`py_compile`);
- existencia do teste do watcher (execucao no PR via `Fast CI - Operational Guardrails`).

## Relatorio de Monitoramento do PR

| Dimensao | Status | Evidencia | Risco | Acao recomendada |
|---|---|---|---|---|
| Escopo alterado | Controlado | Novo workflow e este runbook | Baixo | Manter mudanca pequena e rastreavel |
| Build/CI | Validavel no head do PR | Checks principais do PR devem estar verdes antes do merge | Medio | Bloquear merge se houver falha, cancelamento ou pendencia |
| Testes | Coberto por smoke rapido | Testes do watcher | Baixo | Reexecutar em caso de falha e capturar log |
| Seguranca | Sem alteracao produtiva | Sem deploy e sem ambiente produtivo | Baixo | Nao adicionar permissoes elevadas |
| Observabilidade | Artifact operacional | Evidencia publicada pelo workflow | Baixo | Validar artifact apos execucao em main |
| Documentacao | Atualizada | Runbook com escopo, decisao operacional e tabelas | Baixo | Manter documento sincronizado com o workflow |
| Ambiente | Main pos-merge | Gatilho em push para main | Medio | Usar como evidencia pos-merge |
| Auditoria | Rastreavel | SHA, branch e run id no artifact | Baixo | Preservar retencao do artifact |

## Resultado da Revisao

| Criterio | Resultado | Bloqueia merge? | Observacao |
|---|---|---|---|
| Compilacao YAML | Aprovado quando GitHub Actions aceitar o workflow | Sim, se falhar | Validar no head do PR |
| Testes automatizados | Aprovado quando testes do watcher passarem | Sim, se falhar | Executado no proprio workflow |
| Seguranca minima | Aprovado | Nao | Sem deploy ou producao |
| Governanca | Aprovado | Nao | Incremento operacional pos-PR #131 |
| Documentacao | Aprovado | Nao | Runbook contem escopo, tabelas e evidencia |
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

O artifact main-smoke-ci-evidence contem:

- summary.md com o escopo da validacao;
- evidence.json com branch, SHA, run id e flags de nao alteracao de ambiente.

## Decisao operacional

- Verde: main tem evidencia minima pos-merge.
- Vermelho: bloquear proximo incremento ate capturar log e corrigir a causa raiz.
- Ausencia de run em main: tratar como lacuna de evidencia operacional.

## Relacao com PR CI Watch

O Main Smoke CI complementa a esteira:

1. PR valida antes do merge.
2. Merge integra na main.
3. Main Smoke CI gera evidencia pos-merge.

## Risco reduzido

- Merge sem sinal pos-integracao.
- Falso conforto por checks apenas no PR.
- Falta de artifact rastreavel para a main.
