# Verificação cega do cofre

## Objetivo

Permitir confirmação de igualdade de um segredo sem expor o valor armazenado nem material derivado reutilizável.

## Requisitos

1. Preservar tokens S2S escopados e auditoria existentes.
2. Retornar somente `match` e metadados não sensíveis.
3. Não retornar segredo, digest, HMAC ou fingerprint.
4. Usar chave operacional separada armazenada no próprio cofre.
5. Bloquear leitura, resolução, remoção e verificação da chave operacional.
6. Falhar fechado quando a chave operacional estiver ausente ou fraca.
7. Exigir escopo da chave alvo para tokens escopados.
8. Usar comparação constante no fallback do token global legado.
9. Não registrar valores candidatos ou segredos em auditoria.
10. Nenhum deploy/promoção faz parte deste incremento.

## Critérios de aceite

- testes positivos e negativos verdes;
- teste sem pepper retorna 503;
- token sem escopo retorna 403;
- SDD, segurança e governança verdes;
- `behind_by=0`;
- PR sem conflitos e mergeável.
