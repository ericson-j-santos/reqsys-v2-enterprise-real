# ADR — Verificação cega de valores no cofre

## Status

Implementado de forma compatível com o cofre atual.

## Decisão

O ReqSys oferece `POST /v1/cofre/verificar` para comparar um valor candidato com um segredo armazenado sem devolver o segredo, digest ou fingerprint.

A comparação usa HMAC-SHA-256 com uma chave operacional separada, armazenada no próprio cofre sob `REQSYS_COFRE_VERIFICADOR_PEPPER`. O resultado final usa comparação em tempo constante.

## Integração com o cofre atual

- tokens S2S escopados continuam válidos;
- o token legado usa comparação constante;
- auditoria existente é preservada;
- o token escopado precisa autorizar a chave alvo;
- a chave operacional pode ser gravada por administração, mas não pode ser lida, resolvida, removida ou verificada pelas rotas de lookup;
- ausência ou fraqueza da chave operacional retorna indisponibilidade, sem fallback inseguro.

## Limites

O endpoint confirma igualdade. Ele não transforma o cofre em serviço de autenticação de usuário e não deve ser usado para verificar senhas humanas.
