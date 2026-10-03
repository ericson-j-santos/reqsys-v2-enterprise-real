# Gate note — DEV/STG/PROD

O gate de promoção não substitui o workflow de homologação por ambiente.

Ele consolida as saídas dos ambientes criados em uma única decisão executiva:

- `READY_FOR_PROD_PROMOTION`
- `BLOCKED_FOR_PROD_PROMOTION`

Enquanto as evidências reais de DEV, STG e PROD não forem publicadas, o resultado seguro é bloquear promoção.
