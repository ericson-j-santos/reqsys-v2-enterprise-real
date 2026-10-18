# Requisitos — gitlab-governance-free-hardening

## Contexto

A atestação real do mirror em 18/10/2026 confirmou que a credencial gerenciada
`gitlab-main-mirror` pertence ao bot `user_id=41627393`, membro Maintainer.
O estado observado da `main` continha `allow_force_push=true` e allowances
simultâneos para Maintainers (40) e Developers + Maintainers (30). O primeiro
apply governado desabilitou force-push, mas falhou fechado ao encontrar o
allowance genérico de Developer. O projeto também mantém
`allow_merge_on_skipped_pipeline=true`.

No GitLab Free, usuários individuais não são uma opção geral de
`Allowed to push and merge`; deploy keys e papéis continuam disponíveis.
Portanto, o incremento não deve autoelevar o token nem depender de recurso
Premium. O fallback Maintainer deve ser tratado como limitação explícita, não
como acesso individual equivalente.

## Critérios de aceite

1. Dry-run informa a remoção de registros Developer de push/merge e nunca escreve.
2. Apply remove somente registros de `access_level=30`, usando os IDs retornados
   pelo GitLab e `_destroy=true`, preservando Maintainer e allowances alheios.
3. A remoção é bloqueada se não existir fallback Maintainer, evitando lockout.
4. `allow_force_push` termina `false` e readback detecta falso sucesso.
5. O mirror aceita o bot Maintainer por fallback de papel quando não houver regra
   individual e registra `least_privilege_exact_identity=false`.
6. O provisionador não cria automaticamente allowance individual por `user_id`.
7. O projeto termina com `only_allow_merge_if_pipeline_succeeds=true` e
   `allow_merge_on_skipped_pipeline=false`, comprovados por readback.
8. A identidade Guest legada continua proibida e nome/estado do bot são validados.
9. Testes cobrem casos positivos, dry-run, lockout, developer residual, skipped
   pipeline residual, force-push residual e ausência de allowance.
10. Depois do merge no GitHub, o mirror deve levar o mesmo SHA ao GitLab; dry-run
    GitLab deve executar no SHA espelhado. Apply real e E2E permanecem condicionados
    à validação das pós-condições atuais e não autorizam deploy/prod.
