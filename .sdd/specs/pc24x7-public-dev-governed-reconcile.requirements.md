# PC24x7 DEV público — reconciliação por worktree governado

## Objetivo

Corrigir a reconciliação `public-static` sem sobrescrever o checkout que originou
o runtime atual e sem remover o override Teams que exige credenciais. A operação
continua restrita ao PC24x7 DEV e ao SHA solicitado da `main`.

## Requisitos

1. O checkout descoberto pelos labels do Docker é somente uma fonte de identidade
   e dos overrides locais permitidos. O reconciliador não pode limpar, resetar,
   mesclar ou modificar essa árvore.
2. O código implantado deve vir de um worktree dedicado, registrado no mesmo
   repositório Git, com origem canônica e árvore rastreada limpa.
3. O SHA solicitado deve pertencer a `origin/main`. Um worktree existente somente
   pode avançar por fast-forward; execução obsoleta não pode rebaixar o runtime.
4. Somente os overrides locais `docker-compose.admin-dev.override.yml` e
   `docker-compose.pages-stable.override.yml` podem ser reutilizados. Compose base,
   DEV, Cofre, Teams e frontend público devem vir do worktree governado.
5. O workflow deve autenticar por OIDC no environment `development` e reutilizar
   `reqsys-teams-bot-dev-secret` do Key Vault pelo carregador existente. A
   permissão `id-token: write` fica limitada ao job de reconciliação; o smoke
   público recebe somente `contents: read`. Não é permitido criar, rotacionar,
   imprimir ou persistir o valor.
6. Falhas dos comandos Compose executados com credencial devem produzir somente
   erro sanitizado, sem stdout ou stderr do processo sensível.
7. A reconciliação deve recriar apenas `api`, `frontend` e `nginx` do projeto DEV,
   preservando volumes e overrides locais existentes.
8. A conclusão exige SHA idêntico nos probes direto e gateway, health/readiness
   HTTP 200, frontend estático e `/@vite/client` HTTP 404.
9. HML e PROD permanecem fora de escopo e sem caminho de execução neste workflow.
10. O Runtime Core é opcional neste stack. Sua resolução DNS deve ocorrer somente
    quando uma rota `/runtime-core/` permitida for acessada; a ausência do serviço
    deve retornar HTTP 502 nessas rotas sem impedir o gateway público de iniciar.
    Quando presente, o proxy de TODO events deve preservar sufixo de caminho e query.
11. Depois de reler a autorização recente do owner e antes de qualquer mutação, o
    workflow deve criar somente autorizações Risk3 específicas, temporárias e
    vinculadas ao ambiente DEV, scope, worktree limpo, SHA, script rastreado e
    argumentos exatos. O gateway deve executar o comando cadastrado sem override
    ad-hoc; o modo amplo `standard_gold_development` não pode ser ativado ou alterado.
12. Se o prepare falhar, o handler deve substituir a evidência preflight no mesmo
    `GITHUB_WORKSPACE/artifacts/pc24x7-public-dev/evidence.json` consumido pelo
    upload. `TARGET_PATH` não pode ser usado como raiz do artifact público. Exceção
    inesperada deve persistir somente `cutover_failure_unclassified` e flags
    negativas, sem detalhes, antes de bloquear OIDC, deploy, locator e E2E.
13. Quando o motivo público for `runtime_scope_invalid`, o receipt pode incluir
    somente um `scope_diagnostic_code` estático da allowlist versionada. Para todos
    os demais motivos, o diagnóstico deve ser `not_applicable`. Caminhos, mensagens,
    stdout, stderr, credenciais e dados do banco permanecem proibidos na evidência.

## Critérios de aceite

- o plano Compose real valida com `config --quiet` a partir do worktree limpo;
- a árvore suja original permanece suja e inalterada antes e depois do preflight;
- testes cobrem criação/reuso do worktree, allowlist de overrides, injeção efêmera
  do segredo, redação de erro sensível e menor privilégio por job;
- todos os actions externos do workflow ficam presos a SHAs imutáveis;
- o artifact declara `production_touched=false` e `secret_value_exposed=false`;
- o smoke independente confirma o mesmo SHA publicado antes de considerar DEV pronto.
- o readback de cada autorização específica confirma ambiente DEV, SHA exato,
  expiração curta e `broad_development_mode_changed=false` antes do gateway do owner;
- sem `reqsys-runtime` na rede, o Nginx passa em `nginx -t`, atende frontend/API e
  mantém as rotas permitidas de `/runtime-core/` fechadas com HTTP 502.
- com um upstream stub, `/runtime-core/api/todo-events/abc?x=1` chega ao serviço
  como `/api/todo-events/abc?x=1`.
- os testes estruturais comprovam que o fallback e o upload usam o mesmo
  `GITHUB_WORKSPACE`, recusam o caminho equivalente em `TARGET_PATH` e mantêm
  `runtime_mutated=false` e `production_touched=false`;
- uma exceção inesperada do prepare produz receipt público com
  `reason_code=cutover_failure_unclassified`, sem ecoar a mensagem original.
- cada falha de escopo conhecida preserva apenas seu código estático allowlisted;
  código desconhecido ou motivo não relacionado reduz para `not_applicable`.

## Fora de escopo

- limpar ou recuperar o checkout DEV legado;
- rotacionar a identidade ou o segredo do bot Teams;
- alterar o ambiente, credenciais ou runtime de HML/PROD;
- promover o runtime após DEV.
- ativar automaticamente o modo amplo privado `standard_gold_development`.
