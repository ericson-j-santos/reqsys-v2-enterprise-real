# ADR-033 — Product Intelligence Final Evidence Index

## Status

Proposto.

## Contexto

A frente de Product Intelligence precisa de um índice final de evidências que permita decisões objetivas sobre maturidade técnica, operacional, governança, usuário final e produção.

Sem um índice canônico, a avaliação tende a depender de leitura manual dispersa entre PRs, checks, artifacts, runbooks e ADRs. Isso aumenta risco de falso verde, retrabalho e decisões sem rastreabilidade suficiente.

## Decisão

Criar o **Product Intelligence Final Evidence Index** como artefato documental versionado, com schema JSON, exemplo, runbook operacional e critérios explícitos de bloqueio.

O índice deve registrar evidências com estados textuais e auditáveis, evitando inferir sucesso quando uma validação não foi executada.

## Consequências positivas

- Rastreabilidade objetiva entre PRs, checks, artifacts e decisões.
- Redução de risco de declarar prontidão sem evidência real.
- Melhor separação entre documentação, homologação e produção.
- Base para automação futura de geração JSON/Markdown/HTML.

## Consequências negativas

- Exige manutenção disciplinada das evidências.
- Não substitui validação real em CI, deploy ou ambiente.
- Pode gerar falso senso de maturidade se usado sem checks pós-merge.

## Alternativas consideradas

### Manter evidências apenas em PRs

Rejeitada. PRs isolados não fornecem visão consolidada de maturidade e risco residual.

### Automatizar tudo diretamente em workflow antes do schema

Rejeitada neste incremento. O contrato documental e o schema precisam existir antes da automação para reduzir ambiguidade.

### Declarar Product Intelligence pronta com base em documentação existente

Rejeitada. Prontidão requer evidência real, checks, artifacts e validação pós-merge.

## Guardrails

- Não executar deploy.
- Não alterar secrets.
- Não alterar branch protection.
- Não simular aprovação humana.
- Não declarar produção verde sem evidência real.
- Não fazer merge se CI, conflito, review ou branch protection bloquearem.

## Próximos incrementos

1. Gerador automático do índice em JSON.
2. Renderização Markdown/HTML do índice.
3. Publicação de artifact em GitHub Actions.
4. Gate de validação estrutural do schema.
5. Consolidação pós-merge com evidência da `main`.
