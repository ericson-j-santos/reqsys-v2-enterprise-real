# Noteri ALM runner bridge — requisitos

## Objetivo

Restaurar CI de custo adicional zero para PRs de `ericson-j-santos/reqsys-powerplatform-alm` usando o Noteri já operacional, sem acoplamento a número de PR, branch ou label efêmero específico, sem alterar o runner existente do ReqSys e sem reduzir gates.

## Requisitos

1. A execução deve ocorrer somente no host `Noteri`, Windows x64, em DEV.
2. O repositório alvo permanece fixo em `ericson-j-santos/reqsys-powerplatform-alm` e a base aceita permanece `main`.
3. A ponte deve selecionar automaticamente a PR aberta de menor número cujo HEAD atual possua job GitHub Actions em `queued`, sem `runner_id`, exigindo simultaneamente os labels `self-hosted, Windows, X64, noteri, reqsys-dev`.
4. PR fechada, head repo divergente, base diferente de `main`, branch vazia ou SHA inválido não podem ser selecionados.
5. Após a seleção, `target_pr`, `target_branch` e `expected_head` ficam congelados para toda a execução; qualquer drift falha fechado.
6. Runs `pull_request` ativos da mesma branch em SHA anterior devem ser cancelados antes do registro dos runners para impedir bloqueio de `concurrency` por evidência obsoleta; runs do HEAD atual ou de outra PR não podem ser cancelados.
7. O workflow deve reutilizar `.github/workflows/noteri-desktop-watchdog-recovery.yml` com modo fixo `alm-runner-bootstrap`; nenhum workflow novo deve ser criado e nenhum input livre adicional deve ser introduzido.
8. O Authorized Actions Gateway deve continuar aceitando somente o comando literal `/reqsys run noteri-alm-runner-bootstrap` para essa rota.
9. O job deve usar o runner Noteri já registrado para executar bootstrap, Session Launcher no SHA exato e regras canônicas pinadas.
10. A mutação de registro do runner deve passar exclusivamente por `owner_risk3_gateway.py`, com action fixa e scope limitado ao repositório/ambiente DEV, e autorização temporária removida em `always()`.
11. A ponte deve criar dois runners efêmeros em diretórios separados, sem modificar o runner existente do ReqSys.
12. O GitHub Actions runner deve ser a versão oficial 2.337.0 e o ZIP deve ser validado pelo SHA-256 `1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc` antes da extração.
13. Os runners efêmeros devem usar somente labels estáveis `noteri,reqsys-dev`, além dos labels padrão do runner, com `--ephemeral` e `--disableupdate`; `alm-pr7` não pode existir na implementação.
14. Registration token deve existir somente em memória durante `config.cmd`; não pode ser impresso, persistido ou enviado a artifact.
15. `GH_TOKEN` e `GITHUB_TOKEN` devem ser removidos dos subprocessos que usam o perfil local `gh`.
16. O aceite da ponte exige pickup físico comprovado por `runner_id` e `runner_name` de pelo menos um job do HEAD congelado e todos os workflow runs `pull_request` desse HEAD em estado terminal.
17. A ponte não deve mascarar falha funcional da PR: `target_runs_success` é evidência separada; o objetivo da ponte é comprovar executor/pickup, não transformar check falho em sucesso.
18. O readback final deve ser independente pela API GitHub e `replay_idempotent=true` exige ausência de job Noteri não atribuído no HEAD selecionado.
19. Timeout é obrigatório; ausência de pickup, drift de HEAD ou falta de estado terminal mantém a ponte bloqueada.
20. Nenhuma produção, HML/STG, branch protection, segredo ou billing pode ser alterado.
21. Antes de abrir PR no ReqSys, o Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato e `behind_by=0`.

## Critérios de aceite

- testes contratuais positivos, negativos, seleção determinística, cancelamento de stale run e idempotência aprovados;
- SDD Gate verde;
- Pre-PR Readiness verde no HEAD exato;
- após merge, o comando governado seleciona uma PR elegível sem número hardcoded e produz pickup físico no Noteri;
- a evidência registra PR/branch/SHA selecionados, runners físicos, runs obsoletos cancelados, estado terminal e resultado funcional separado;
- readback final confirma o mesmo HEAD e nenhum segredo/token é exposto.
