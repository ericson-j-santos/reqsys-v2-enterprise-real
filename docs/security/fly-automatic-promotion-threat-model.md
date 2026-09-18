# Threat model — promoção automática Fly

## Ameaças controladas

- promoção de SHA obsoleto;
- salto de DEV/STG;
- bypass do gate BACEN;
- bypass do environment GitHub;
- artifact ausente tratado como sucesso;
- runtime saudável, porém com SHA incorreto;
- secret obrigatório ausente;
- vazamento de valores de secrets em artifacts;
- configuração Fly divergente;
- check degradado ignorado;
- execução concorrente de promoções.

## Controles

- comparação exata com `origin/main`;
- dependências sequenciais de jobs;
- BACEN Production Hard Gate reutilizável;
- environments `dev`, `staging` e `production`;
- decisão fail-closed;
- captura sanitizada;
- concurrency sem cancelamento de deploy ativo;
- validação estrita após cada deploy.

## Risco residual

Falhas externas do Fly.io, indisponibilidade transitória e aprovações pendentes podem interromper a cadeia. O workflow preserva evidências e não converte falha operacional em autorização.
