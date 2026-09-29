# Noteri ALM runner bridge — requisitos

## Objetivo

Restaurar CI de custo adicional zero para o PR #7 de `ericson-j-santos/reqsys-powerplatform-alm` usando o Noteri já operacional, sem alterar o runner repo-scoped existente do ReqSys e sem reduzir gates.

## Requisitos

1. A execução deve ocorrer somente no host `Noteri`, Windows x64, em DEV.
2. O alvo é fixo: repositório `ericson-j-santos/reqsys-powerplatform-alm`, PR #7, base `main` e branch `diag/outlook-connection-probe-20260928`; o HEAD deve ser resolvido pela API no início de cada execução, validado como SHA completo e congelado como `expected_head` para todo o E2E.
3. O workflow deve reutilizar `.github/workflows/noteri-desktop-watchdog-recovery.yml` com modo `alm-runner-bootstrap`; nenhum workflow novo deve ser criado.
4. O Authorized Actions Gateway deve aceitar somente o comando literal `/reqsys run noteri-alm-runner-bootstrap`.
5. O job deve usar o runner Noteri já registrado para executar o bootstrap, Session Launcher no SHA exato e regras canônicas pinadas.
6. A mutação de registro do runner deve passar exclusivamente por `owner_risk3_gateway.py`, com action e scope fixos e autorização temporária removida em `always()`.
7. A ponte deve criar runners efêmeros em diretórios separados, sem modificar o runner existente do ReqSys.
8. O GitHub Actions runner deve ser a versão oficial 2.337.0 e o ZIP deve ser validado pelo SHA-256 `1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc` antes da extração.
9. Os runners efêmeros devem usar labels `noteri,reqsys-dev,alm-pr7`, `--ephemeral` e `--disableupdate`.
10. Registration token deve existir somente em memória durante `config.cmd`; não pode ser impresso, persistido ou enviado a artifact.
11. `GH_TOKEN` e `GITHUB_TOKEN` devem ser removidos dos subprocessos que usam o perfil local `gh`.
12. O script deve recusar PR fechado, base/repositório/branch divergentes ou SHA inválido; depois de resolver o HEAD atual, deve recusar qualquer mudança desse HEAD durante ou antes do readback final.
13. O aceite exige os dois workflows do PR no mesmo HEAD em `completed/success`: `Build and Deploy to Test` e `Power Platform Outlook Connection Read-only Probe`.
14. O readback final deve ser independente pela API GitHub e o replay no estado já verde deve retornar `ALREADY_COMPLIANT` sem novo registro.
15. Timeout é obrigatório; ausência de conclusão ou falha de qualquer check mantém o estado bloqueado.
16. Nenhuma produção, HML/STG, branch protection, segredo ou billing pode ser alterado.
17. Antes de abrir PR no ReqSys, o Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato e `behind_by=0`.

## Critérios de aceite

- testes contratuais positivos, negativos e de idempotência aprovados;
- SDD Gate verde;
- Pre-PR Readiness verde no HEAD exato;
- após merge, o comando governado produz pickup físico no Noteri;
- os dois checks do PR #7 executam no HEAD exato e ficam verdes;
- readback final confirma o mesmo HEAD e nenhum segredo/token é exposto.
