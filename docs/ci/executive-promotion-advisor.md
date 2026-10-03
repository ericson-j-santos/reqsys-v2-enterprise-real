# Executive Promotion Advisor

## Objetivo

Consolidar os principais sinais executivos do ReqSys e emitir uma recomendação única de promoção sem alterar merge, deploy ou produção.

## Decisões

- `READY`: todos os domínios avaliados estão verdes.
- `REVIEW`: existe domínio amarelo ou sem evidência suficiente.
- `HOLD`: existe domínio vermelho.

## Entradas

- Runtime Executive Index;
- Executive Readiness;
- Security Executive Summary;
- Merge Readiness;
- histórico de homologação do Workflow Efficiency.

## Saída

Artifact `executive-promotion-advisor`, contendo:

- decisão;
- confiança percentual;
- estados por domínio;
- domínios de risco;
- recomendação textual;
- `correlation_id`;
- exigência de aprovação humana.

## Guardrails

O advisor opera sempre com:

- `mode=report-only`;
- `production_blocker=false`;
- `human_approval_required=true`.

Ele não altera deploy, merge queue, auto-merge, branch protection ou decisão global do Executive Readiness.

## Evolução futura

Qualquer promoção para ação automática exige histórico real, política versionada, aprovação humana, rollback documentado e PR separado.
