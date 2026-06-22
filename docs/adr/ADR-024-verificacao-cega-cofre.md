# ADR-024 — Verificacao cega do cofre

## Status

Proposto.

## Decisao

Adicionar endpoint de verificacao cega para casos em que a aplicacao precisa validar se um valor informado corresponde ao valor armazenado no cofre, sem retornar o valor armazenado.

## Controles

- Retornar apenas `match` verdadeiro ou falso.
- Nao retornar valor bruto.
- Nao retornar resumo criptografico, hash, digest ou fingerprint.
- Usar comparacao resistente a timing attack.
- Usar segredo operacional separado para derivacao.
- Bloquear chaves internas do proprio mecanismo.

## Criterio de pronto

- Testes unitarios e de API cobrindo match verdadeiro, falso, chave inexistente, chave reservada e ausencia do segredo operacional.
- CI completo verde.
- PR em draft ate revisao e autorizacao explicita.
