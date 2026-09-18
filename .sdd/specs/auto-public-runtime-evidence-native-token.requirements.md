# Auto Public Runtime Evidence — token efêmero nativo

## Contexto

A execução 35377738842 falhou ao solicitar `actions:write` para a GitHub App configurada. A instalação respondeu HTTP 422 porque essa permissão não está concedida.

O workflow já executa dentro do GitHub Actions e pode usar o `GITHUB_TOKEN` efêmero do próprio job com escopo declarado no YAML, eliminando dependência de PAT ou chave privada para este dispatch.

## Requisitos

1. O workflow deve declarar somente `actions: write` e `contents: read`.
2. Nenhum `GH_PAT_ACTIONS`, App ID ou chave privada de GitHub App deve ser consumido nesse caminho.
3. Todo comando `gh` autenticado deve usar `${{ github.token }}`.
4. Antes do dispatch, uma leitura autenticada deve confirmar que `public-runtime-evidence.yml` está `active`.
5. Ausência de token, falha da leitura ou workflow alvo não ativo deve falhar fechado antes do dispatch.
6. Os inputs `public_url`, `strict`, `publish_comment`, `issue_number` e `ref` devem ser preservados.
7. O workflow não deve imprimir o valor do token.

## Critérios de aceite (Acceptance Criteria)

1. `tests/test_auto_public_runtime_evidence_token_contract.py` passa.
2. O teste prova que PAT e credenciais de GitHub App não aparecem no workflow.
3. O teste prova a permissão mínima `actions:write + contents:read`.
4. O teste prova que a validação autenticada ocorre antes do dispatch.
5. O teste prova que todos os usos de `GH_TOKEN` apontam para `${{ github.token }}`.
6. O SDD Gate passa no HEAD exato.
7. O Pre-PR Readiness passa no HEAD exato e com a branch não atrasada em relação à `main`.
