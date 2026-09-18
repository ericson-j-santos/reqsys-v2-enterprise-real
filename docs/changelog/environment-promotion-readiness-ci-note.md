# CI note — Environment Promotion Readiness

O workflow `environment-promotion-readiness.yml` roda em PR quando o contrato, testes ou evidências relacionadas mudarem.

Em PR, o modo padrão é report-only para não executar deploy real em DEV/STG/PROD.

Para uma homologação real por ambiente, usar o workflow existente `fly-environment-homologation-gate.yml` com o ambiente alvo.
