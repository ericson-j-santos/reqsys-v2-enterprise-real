# Deferred Institutional Approval

## Objetivo

Permitir evolução técnica do ReqSys durante desenvolvimento e pré-oficialização sem fabricar evidência de aprovação institucional, mantendo aprovação formal como gate obrigatório antes de produção ou adoção institucional.

## Estados

`DRAFT -> TECHNICALLY_IMPLEMENTED -> PENDING_INSTITUTIONAL_APPROVAL -> APPROVED -> OPERATIONAL`

## Regra de pré-produção

Quando `lifecycle_stage` não for `PRODUCTION` nem `INSTITUTIONAL`:

- `approval_authority` pode permanecer `pending_formal_designation`;
- `approval_record` pode permanecer nulo;
- a ausência desses campos não gera pendência humana imediata;
- o status máximo permitido é `technically_implemented`;
- nenhuma automação pode declarar aprovação institucional ou conformidade plena.

## Gate de produção

Quando houver promoção para `PRODUCTION` ou `INSTITUTIONAL`, tornam-se obrigatórios:

- autoridade aprovadora formal;
- registro/referência verificável da aprovação;
- data da aprovação institucional.

A promoção deve ser bloqueada enquanto qualquer desses campos estiver ausente.

## Notificação humana

A rotina de pendências humanas deve suprimir solicitações de autoridade/atestado enquanto o lifecycle estiver em desenvolvimento. A pendência deve ser reativada automaticamente quando houver intenção de promoção para produção ou institucionalização.

## Evidência e segurança

Evidência técnica não equivale a aprovação institucional. Referências devem ser não sensíveis e documentos assinados ou segredos não devem ser replicados no repositório público.

## Rollback

Reverter os commits deste incremento restaura a política anterior. `production_touched=false`.
