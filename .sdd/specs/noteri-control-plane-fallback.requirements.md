# Noteri — fallback independente do plano de controle

## Objetivo

Manter uma rota governada de execução quando o Remote Desktop Commander estiver indisponível ou com cota esgotada, sem usar GUI, mouse, teclado, clipboard ou shell arbitrário.

## Classificação

`gap_fix`.

## Arquitetura

1. O GitHub Authorized Actions Gateway continua como origem externa governada.
2. O Noteri recebe um GitHub Actions runner self-hosted dedicado com labels fixos `[self-hosted, Windows, X64, noteri, reqsys-dev]`.
3. O watchdog local `noteri_control_plane_watchdog.py` mantém um runner previamente configurado ativo e persiste no boot por tarefa `AtStartup + S4U`.
4. O workflow `noteri-control-plane-probe.yml` prova pickup real, host exato e `Runner.Listener.exe` sem depender de RDC.
5. O Gateway aceita somente o comando exato `/reqsys run noteri-control-plane-probe`.
6. O Gateway aguarda pickup e falha fechado com `SELF_HOSTED_RUNNER_UNAVAILABLE` se o runner não adquirir o job.
7. Quando não houver pickup, o Gateway cancela o run self-hosted abandonado, confirma `completed/cancelled` por janela limitada e registra o resultado da limpeza; nenhuma nova tentativa é criada automaticamente.

## Requisitos

- executar somente no host exato `Noteri`;
- local/DEV somente;
- não ler conteúdo de `.runner`;
- não armazenar token de registro, senha ou segredo;
- não executar reboot/shutdown;
- não expor comando arbitrário;
- usar source SHA completo na instalação do watchdog;
- release local imutável sob `%LOCALAPPDATA%\ReqSys\NoteriControlPlaneWatchdog\releases\<sha>`;
- persistir evidência sanitizada;
- declarar `rdc_required=false`, `production_touched=false` e `secrets_read=false`;
- se Task Scheduler negar `AtStartup + S4U`, retornar `activation_pending=true` e não declarar ativação concluída.

## Pré-requisito físico

O GitHub Actions runner precisa estar registrado uma vez no Noteri antes de o watchdog poder mantê-lo ativo. O watchdog valida a presença de `.runner`, `run.cmd` e `bin\Runner.Listener.exe`, mas nunca lê o conteúdo de `.runner`.

## Critérios de aceite de código

- testes unitários do probe/watchdog verdes;
- governance de self-hosted runner verde;
- Gateway continua com allowlist estática;
- workflow sem inputs arbitrários;
- CI do PR verde no SHA atual.

## Critérios de aceite runtime

A rota só fica `runtime_active` após evidência nova de:

1. runner registrado no Noteri com labels fixos;
2. watchdog com tarefa `AtStartup + S4U`;
3. `Runner.Listener.exe` ativo;
4. comando do Gateway despachando `noteri-control-plane-probe.yml`;
5. workflow saindo de queued/pending e executando no Noteri;
6. artifact mostrando `ok=true`, host Noteri e `rdc_required=false`.
7. em caso negativo sem pickup, o run alvo termina cancelado (ou a falha de cancelamento fica explicitamente registrada), sem fila residual criada pelo Gateway.

Sem esses itens o estado permanece `activation_pending`.
