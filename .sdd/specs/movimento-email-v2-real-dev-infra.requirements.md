# Movimento Email V2 — infraestrutura DEV e fonte canônica

## Requisito 1 — remover o stub da V2
As quatro views V2 devem consultar tabelas persistentes da camada canônica `movimento_src` e não podem conter `WHERE 1 = 0`.

## Requisito 2 — infraestrutura DEV autocontida
Deve existir bootstrap local/DEV capaz de criar o banco dedicado, o schema `movimento_src`, as quatro tabelas-fonte e as quatro views sem criar login, usuário, segredo ou permissão administrativa.

## Requisito 3 — não inventar o SSRS corporativo
A V2 não deve alegar que conhece o schema legado. O mapeamento corporativo deve permanecer uma integração separada: SSRS/SQL real → `movimento_src.*`.

## Requisito 4 — idempotência e rollback
Bootstrap, criação de tabelas e `CREATE OR ALTER VIEW` devem ser repetíveis. O rollback V2 deve restaurar o contrato V1 sem depender do datasource corporativo.

## Requisito 5 — segurança
Dados E2E devem ser sintéticos e identificáveis. Nenhuma credencial, DSN completo, CPF real ou dado corporativo pode ser versionado.

## Critérios de aceite (Acceptance Criteria)
1. As quatro V2 referenciam exatamente as quatro tabelas `movimento_src.*` e não usam stub.
2. `scripts/bootstrap_movimento_email_dev.py --seed-e2e` cria/reutiliza a infraestrutura DEV sem segredos.
3. O E2E SQL cria as quatro views, retorna 2/1/1/1 registros para a data sintética e 0 para a data negativa.
4. Reexecutar o bootstrap preserva as mesmas contagens, comprovando idempotência.
5. Os SHA-256 da V2 batem com `MANIFEST.json`.
6. O teste `tests/test_movimento_email_v2_sql.py` passa.
7. O Pre-PR Readiness Gate passa no HEAD exato antes da abertura da PR.
8. A validação DEV não deve ser apresentada como evidência de datasource corporativo; a integração externa permanece pendente até haver `server + database` ou `.rdl/.rds`.
