# Cofre — verificação cega v1

## Entrega

- endpoint `POST /v1/cofre/verificar`;
- HMAC com chave operacional separada;
- comparação constante;
- compatibilidade com tokens S2S escopados;
- auditoria preservada;
- chave operacional não recuperável pelas rotas de lookup;
- testes positivos, negativos, fail-closed e de escopo.

Nenhum segredo, digest ou fingerprint é retornado pelo endpoint.
