# PR #145 — Resolução de conflito

## Contexto

O PR #145 ficou não mergeável após avanço da `main` em arquivos de CI/governança também alterados pelo PR.

## Estratégia aplicada

Como a branch original exigia atualização por merge/rebase e a movimentação forçada do ref foi bloqueada pela camada de segurança operacional, foi criada uma branch limpa baseada na `main` atual:

- `repair/pr145-clean-main-base`

A branch reaplica o escopo funcional do PR #145:

- neutralização do `.coderabbit.yaml`;
- workflow `PR Quality Review`;
- script `scripts/pr_quality_review.py`;
- ADR de substituição do CodeRabbit;
- compatibilização do `PR CI Watch` com política não bloqueante para `pending/warning`;
- testes alinhados.

## Decisão operacional

Usar o PR substituto limpo como continuação objetiva do PR #145, evitando conflito recorrente e preservando rastreabilidade.
