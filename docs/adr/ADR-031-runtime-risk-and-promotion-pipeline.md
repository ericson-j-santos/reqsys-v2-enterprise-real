# ADR-031 — Runtime Risk Scoring e Governed Promotion Pipeline

## Status

Aceita para incremento inicial.

## Contexto

Após a criação do Governed Dev Auto Merge, o ReqSys precisa evoluir para uma cadeia mais madura de decisão operacional:

- classificar risco de PR antes de merge/promoção;
- diferenciar dev, homologação e produção;
- gerar evidência auditável;
- impedir promoção produtiva sem aprovação humana;
- preparar integração futura com DORA metrics, Change Failure Rate e Runtime Approval Center.

## Decisão

Criar dois workflows:

1. `Runtime Risk Scoring`: executado em PRs e manualmente, produzindo artifact com score de risco.
2. `Governed Promotion Pipeline`: executado manualmente para simular ou preparar promoção entre ambientes.

## Regras

### Dev

- Auto-merge governado permitido apenas por workflow específico.
- Deve usar score de risco e gates complementares em incrementos futuros.

### Homologação

- Promotion pipeline pode criar PR draft de promoção quando `dry_run=false` e a política aprovar.
- Alterações sensíveis bloqueiam promoção automática para homolog.

### Produção

- Promoção real para produção permanece bloqueada neste incremento.
- Produção exige `change_ticket` e confirmação textual `APROVO-PROD` mesmo para simulação.
- Qualquer execução real futura deve usar environment approval, rollback metadata e validação pós-deploy.

## Consequências positivas

- Cria sinal objetivo de risco por PR.
- Melhora tomada de decisão antes de merge.
- Evita tratar dev/homolog/prod da mesma forma.
- Gera artifacts rastreáveis.
- Prepara base para analytics operacional e DORA.

## Consequências negativas

- O score inicial é heurístico e deve ser calibrado com dados reais.
- O pipeline de produção ainda não executa promoção real.
- Promotion para homolog depende da existência da branch alvo.

## Critério de evolução

O próximo incremento deve integrar o `risk-score.json` ao Actions Center / Runtime Intelligence para visualização operacional.