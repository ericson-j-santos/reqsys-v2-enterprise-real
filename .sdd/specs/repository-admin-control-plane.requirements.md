# Repository Admin Control Plane — Requisitos

## Objetivo

Consolidar a issue #115 em uma superfície read-only para administrar o estado de
repositórios sem duplicar Merge Console, PR CI Watch, Pre-PR Readiness ou
Governed Merge Queue.

## Requisitos

1. O registry deve ser declarativo, versionado e validar nomes `owner/repo`.
2. O P0 deve operar somente em modo `read_only`.
3. O snapshot deve resolver a branch padrão e registrar o SHA exato observado.
4. A decisão de PR deve estar vinculada a `repository + PR + head_sha`.
5. Check `skipped` ou `neutral` não pode ser tratado como evidência verde.
6. Falha de CI deve produzir `fix_ci`; CI em execução deve produzir `wait_ci`.
7. Conflito deve produzir `blocked_conflict`.
8. Ausência de checks deve produzir `no_ci_evidence`.
9. Estado integralmente verde deve produzir somente `ready_for_full_gates`;
   não deve autorizar merge, deploy ou outra mutação.
10. As rotas devem exigir `require_admin`.
11. Erros do GitHub devem falhar fechado e retornar erro de integração.
12. Nenhum segredo, branch protection, merge, retry, deploy ou promoção deve ser
    alterado por este incremento.

## Critérios de aceite

- registry rejeita duplicidade;
- snapshot comprova SHA exato;
- teste negativo comprova que `skipped` não vira verde;
- decisão classifica CI falho e CI verde de forma determinística;
- API retorna snapshot governado para repositório registrado;
- repositório fora do registry é rejeitado;
- Pre-PR Readiness deve passar no HEAD final e comprovar `behind_by=0`.
