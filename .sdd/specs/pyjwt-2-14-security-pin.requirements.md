# PyJWT 2.14.0 security pin

## Objetivo

Remover a vulnerabilidade detectada pelo `pip-audit` em `PyJWT==2.13.0` e manter os três pins canônicos do ReqSys alinhados na release corrigida `2.14.0`.

## Requisitos

1. `backend/requirements.txt` deve usar exatamente `PyJWT==2.14.0`.
2. `backend/requirements-audit.txt` deve usar exatamente `PyJWT==2.14.0`.
3. `backend/token_broker/requirements.txt` deve usar exatamente `PyJWT==2.14.0`.
4. Nenhum dos três arquivos pode manter `PyJWT==2.13.0`.
5. A atualização não altera algoritmo, issuer, audience, chaves, segredos ou configuração de autenticação.
6. O CI deve voltar a passar `pip-audit` sem suppress/ignore da vulnerabilidade.
7. Testes backend existentes devem continuar verdes.

## Controles negativos

- Alterar somente `requirements-audit.txt` é inválido, pois deixaria runtime e auditoria divergentes.
- Ignorar CVE, desabilitar `pip-audit` ou adicionar allowlist para a vulnerabilidade não satisfaz o requisito.
- Qualquer regressão de autenticação nos testes existentes bloqueia o merge.

## Critérios de aceite

- `tests/test_pyjwt_security_pin.py` verde.
- `pip-audit` do CI principal verde.
- Testes backend do mesmo HEAD verdes.
- Pre-PR Readiness verde no HEAD final e `behind_by=0`.
