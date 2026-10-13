# Contrato de autenticação do DEV público PC24x7 — requisitos

## Contexto

O runtime público ReqSys DEV na porta 8210 deve manter o login demonstrativo desativado. A composição pública já fixa `ALLOW_DEMO_LOGIN=false`, porém rotas compartilhadas de recriação podem omitir o overlay. O ambiente `dev` não distingue runtime público de execução local legada.

## Critérios de aceite

1. O perfil público é comprovado por host, projeto Compose `wt-pc24x7-piloto`, serviço `api`, vínculo único `8210 -> 8000`, working directory e lista ordenada de arquivos Compose observados.
2. `APP_ENV=dev`, ausência de overlay ou caminho do checkout isoladamente não provam identidade pública ou local.
3. Docker remoto, caminhos UNC, drive-relative, traversal, ADS, symlink, junction ou reparse point no overlay/ancestrais bloqueiam antes de sync, segredo ou mutação.
4. O overlay `docker-compose.pc24x7-public-dev.yml` precisa ser arquivo versionado do checkout observado e continuar presente após sync.
5. A composição renderizada precisa resolver `ALLOW_DEMO_LOGIN=false` antes de `docker compose up`; o payload integral de Compose nunca é salvo ou impresso.
6. Após recriação, container e `http://127.0.0.1:8210/v1/auth/config` precisam concordar estritamente em `false`, com HTTP 200, envelope `data` e sem redirect, proxy ou fallback.
7. Falha posterior ao recreate registra `mutation_performed=true` e `validation_failed_after_mutation=true`; não é apresentada como bloqueio anterior ou rollback.
8. O override programático de SHA contém exclusivamente `GITHUB_SHA`.
9. O provisionador legado que depende de demo login recusa o alvo público antes de sync, Key Vault, recreate ou E2E.
10. Demo login local permanece opt-in; nenhum default global de autenticação é alterado.
11. Evidência e erros expõem apenas identidade, projeto, porta, nomes Compose, SHA e booleanos sanitizados; nunca env, Compose integral, segredo ou credencial.
12. A ausência do overlay observado é prevenção fail-closed. Reparar o runtime físico atual requer diagnóstico e autorização posteriores.
13. Nenhum deploy, restart, alteração de runtime, identidade, credencial, permissão ou proteção faz parte deste incremento.
