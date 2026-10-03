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
   `reqsys-teams-bot-dev-secret` do Key Vault pelo carregador existente. Não é
   permitido criar, rotacionar, imprimir ou persistir o valor.
6. Falhas dos comandos Compose executados com credencial devem produzir somente
   erro sanitizado, sem stdout ou stderr do processo sensível.
7. A reconciliação deve recriar apenas `api`, `frontend` e `nginx` do projeto DEV,
   preservando volumes e overrides locais existentes.
8. A conclusão exige SHA idêntico nos probes direto e gateway, health/readiness
   HTTP 200, frontend estático e `/@vite/client` HTTP 404.
9. HML e PROD permanecem fora de escopo e sem caminho de execução neste workflow.

## Critérios de aceite

- o plano Compose real valida com `config --quiet` a partir do worktree limpo;
- a árvore suja original permanece suja e inalterada antes e depois do preflight;
- testes cobrem criação/reuso do worktree, allowlist de overrides, injeção efêmera
  do segredo e redação de erro sensível;
- todos os actions externos do workflow ficam presos a SHAs imutáveis;
- o artifact declara `production_touched=false` e `secret_value_exposed=false`;
- o smoke independente confirma o mesmo SHA publicado antes de considerar DEV pronto.

## Fora de escopo

- limpar ou recuperar o checkout DEV legado;
- rotacionar a identidade ou o segredo do bot Teams;
- alterar o ambiente, credenciais ou runtime de HML/PROD;
- promover o runtime após DEV.
