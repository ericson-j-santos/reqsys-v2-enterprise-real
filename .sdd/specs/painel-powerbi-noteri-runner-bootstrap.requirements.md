# Painel Power BI — Runner Noteri Dedicado

## Objetivo

Registrar e manter online, sem custo e sem interferir no runner ReqSys existente, um segundo GitHub Actions runner no host Noteri dedicado ao repositório `ericson-j-santos/painel-powerbi`.

## Classificação

`gap_fix` operacional DEV.

## Requisitos

1. Executar somente no host `Noteri` e no runner allowlisted `[self-hosted, Windows, X64, noteri, reqsys-dev]`.
2. O workflow deve existir apenas para a branch operacional fixa `ops/painel-powerbi-noteri-runner-bootstrap-20260928`; não executar em `pull_request`.
3. O runner alvo deve usar nome fixo `Noteri-PainelPowerBI`, repositório fixo `ericson-j-santos/painel-powerbi` e home separado em `%LOCALAPPDATA%\PainelPowerBI\NoteriGitHubRunner`.
4. Não reconfigurar, parar ou substituir o runner do ReqSys.
5. Obter `registration-token` efêmero via autenticação local `gh`, removendo `GH_TOKEN` e `GITHUB_TOKEN` do ambiente do subprocesso.
6. Nunca persistir nem imprimir registration-token.
7. Usar binário oficial do GitHub Actions Runner versão pinada e validar SHA-256 antes da extração.
8. Iniciar o listener dedicado em processo destacado sem herdar `RUNNER_TRACKING_ID`.
9. Sucesso terminal exige readback no GitHub com nome exato, status `online` e labels mínimas `self-hosted, Windows, X64, noteri, reqsys-dev, painel-powerbi`.
10. Não tocar produção, Desktop, RDC, segredo Fabric ou configuração de aplicação.
11. Reexecução deve ser idempotente: runner já online/labels corretas não é recriado.

## Critérios de aceite

- teste de contrato focado verde no próprio runner Noteri;
- workflow na allowlist self-hosted;
- execução física no HEAD exato da branch;
- readback GitHub do runner dedicado como `online`;
- o job já enfileirado no `painel-powerbi` deve demonstrar pickup posterior.
