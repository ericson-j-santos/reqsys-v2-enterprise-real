# ADR — Promoção automática sequencial de ambientes Fly

## Status

Aceita em implementação governada.

## Contexto

A detecção de drift existia, mas a implantação exigia intervenção manual e as evidências estavam distribuídas entre workflows. Isso aumentava lead time e permitia decisões operacionais sem uma captura única correlacionada.

## Decisão

Usar uma cadeia sequencial baseada no SHA atual da `main`, com captura fail-closed antes e depois de cada deploy. DEV e STG podem ser promovidos automaticamente quando houver drift. PROD exige STG verde, BACEN Production Hard Gate e regras do environment GitHub.

## Consequências

- redução de intervenção manual;
- evidências auditáveis por estágio;
- interrupção imediata diante de inconsistência;
- produção permanece governada;
- rollback continua separado e explícito;
- aumento controlado da complexidade dos reusable workflows.
