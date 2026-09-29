# Runner repo-scoped do `diversos` no Noteri

## Objetivo

Disponibilizar, em ambiente local/DEV e sem custo adicional, um GitHub Actions runner
exclusivo para `ericson-j-santos/diversos`, executado no host `Noteri`, sem alterar
visibilidade do repositório nem reduzir gates de CI.

## Requisito 1 — alvo fixo

A automação deve aceitar somente:
- host `Noteri`;
- repositório `ericson-j-santos/diversos`;
- runner `Noteri-diversos`;
- labels `noteri,diversos-dev`;
- ambiente `dev`.

Nenhum repositório, host, runner ou ambiente pode ser recebido por input livre.

## Requisito 2 — runner oficial e pinado

O runner deve usar `actions/runner` versão `2.337.0` e validar o SHA-256
`1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc`
antes de extrair os binários.

## Requisito 3 — autorização administrativa temporária

O registro do runner é Risk3 e deve passar por `owner_risk3_gateway.py`, usando a
ação exata `reqsys.noteri-diversos-runner-bootstrap.dev`, escopo fixo
`repo://ericson-j-santos/diversos/actions/runner/noteri-diversos`, validade máxima
de 30 minutos e referência de autorização `chat-20260928-diversos-noteri-dev`.

## Requisito 4 — credencial efêmera

O token de registro deve ser solicitado apenas ao endpoint oficial do GitHub usando
a autenticação local já existente do `gh`, consumido somente em memória, nunca
persistido e nunca impresso. `GH_TOKEN` e `GITHUB_TOKEN` herdados devem ser
removidos dos subprocessos.

## Requisito 5 — persistência e pickup

A configuração deve criar/reutilizar um diretório dedicado ao runner do `diversos`,
preservar o runner ReqSys já existente, instalar inicialização no escopo do usuário
e comprovar por leitura independente do registro GitHub que `Noteri-diversos` está
`online` com todas as labels exigidas.

## Requisito 6 — idempotência e controle negativo

A mesma execução deve repetir o provisionamento uma segunda vez e comprovar zero
nova mutação. Host divergente, autorização divergente, identidade GitHub divergente,
SHA do runner divergente ou registro associado a outro repositório devem falhar
fechado.

## Critérios de aceite

1. Testes unitários/contratuais aprovam alvo fixo, controle negativo, labels,
   pinning, Risk3 e ausência de exposição de token.
2. `Pre-PR Readiness Gate` retorna `READY_FOR_PR=passed` no HEAD exato e
   `behind_by=0` antes da abertura da PR.
3. Após integração, o workflow físico é disparado via Authorized Actions Gateway.
4. O artifact sanitizado confirma `NOTERI_DIVERSOS_RUNNER_READY`,
   `replay_idempotent=true`, repository/host/runner exatos e runner online.
5. O CI de `ericson-j-santos/diversos#12` só pode ser considerado desbloqueado
   depois de pickup real do runner no SHA atual do PR.
