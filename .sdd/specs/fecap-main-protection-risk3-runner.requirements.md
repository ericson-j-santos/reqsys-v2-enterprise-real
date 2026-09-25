# Runner Risk3 fixo para proteção da main do FECAP

## Objetivo

Preparar, no Engineering Control Plane, o executor administrativo mínimo para proteger `ericson-j-santos/fecap-clipping-automation@main` sem expor uma operação genérica de administração de repositórios.

## Requisitos

1. O alvo deve ser fixo em `ericson-j-santos/fecap-clipping-automation` e branch `main`.
2. O ruleset deve ser fixo em `main-protection`.
3. O executor permitido deve ser o host `Noteri` dentro de uma sessão governada.
4. A ação Risk3 deve usar `reqsys.fecap-main-protection.dev` e escopo `repo://ericson-j-santos/fecap-clipping-automation/branch/main`.
5. Repository, branch, ruleset e required check não podem ser recebidos por parâmetros livres.
6. A autenticação GitHub deve usar o perfil local existente do `gh`; subprocessos devem remover `GH_TOKEN` e `GITHUB_TOKEN`.
7. Antes da escrita, o FECAP/main deve estar exatamente em `2b72e45012faeef84d1828faa97b7b8d4efd968f`.
8. O source SHA validado `c756b4faa948a9a23f3faf09e2e5cf748914a5fd` deve ser parent do merge commit alvo.
9. O check `tests` do source SHA deve estar `completed/success`.
10. O ruleset deve exigir Pull Request, stale reviews dismissed, linear history, `tests` strict, bypass vazio e bloquear force-push/exclusão.
11. Após a mutação, branch e ruleset devem ser relidos; `protected=true` e conformidade integral são obrigatórios.
12. O SHA da branch deve permanecer estável antes/depois.
13. Replay deve ser idempotente quando o ruleset já estiver conforme.
14. A evidência não pode expor token, senha ou API key.
15. Este incremento não declara o wiring de workflow/dispatch concluído enquanto a ferramenta conectada bloquear a alteração de `.github/workflows/branch-protection-audit.yml`.

## Critérios de aceite

- testes de contrato do runner verdes;
- nenhuma superfície administrativa genérica criada;
- alvo e pré-condições amarrados aos SHAs evidenciados do FECAP;
- readback independente implementado;
- nenhum segredo persistido;
- PR permanece draft enquanto o E2E administrativo não puder ser executado.
