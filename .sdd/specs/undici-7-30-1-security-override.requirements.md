# Undici 7.30.1 security override

## Objetivo

Remover as vulnerabilidades detectadas pelo `npm audit` em `undici 7.30.0`, dependência transitiva de `jsdom`, mantendo a árvore do frontend determinística.

## Requisitos

1. `frontend/package.json` deve fixar o override de `undici` exatamente em `7.30.1`.
2. `frontend/package-lock.json` deve resolver `node_modules/undici` exatamente para `7.30.1`.
3. O lockfile deve registrar a URL e a integridade oficiais da release `7.30.1`.
4. A atualização não deve alterar a versão declarada de `jsdom` nem outras dependências.
5. O CI deve executar `npm audit --audit-level=high` sem suppress, ignore ou allowlist.
6. Build e testes unitários existentes do frontend devem permanecer verdes.

## Controles negativos

- Manter o override ou o lockfile em `7.30.0` é inválido.
- Ignorar as advisories ou reduzir o nível do audit não satisfaz o requisito.
- Atualizar dependências não relacionadas bloqueia o merge.

## Critérios de aceite

- `tests/test_undici_security_override.py` verde.
- `npm audit --audit-level=high` retorna zero vulnerabilidades.
- `npm run test:unit` e `npm run build` verdes no mesmo HEAD.
- Pre-PR Readiness e contrato SDD verdes no HEAD final.
