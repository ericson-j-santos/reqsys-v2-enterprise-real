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
5. O Gateway aceita somente os comandos exatos `/reqsys run noteri-control-plane-probe` e `/reqsys run noteri-headless-control-plane-activation`.
6. O Gateway aguarda pickup e falha fechado com `SELF_HOSTED_RUNNER_UNAVAILABLE` se o runner não adquirir o job.
7. Quando não houver pickup, o Gateway cancela o run self-hosted abandonado, confirma `completed/cancelled` por janela limitada e registra o resultado da limpeza; nenhuma nova tentativa é criada automaticamente.

## Requisitos

- executar somente no host exato `Noteri`;
- local/DEV somente;
- não ler conteúdo de `.runner`;
- token de registro efêmero pode ser consumido somente em memória no bootstrap; é proibido imprimir, persistir, versionar ou incluir esse valor na evidência;
- não executar reboot/shutdown;
- não expor comando arbitrário;
- usar source SHA completo na instalação do watchdog;
- release local imutável sob `%LOCALAPPDATA%\ReqSys\NoteriControlPlaneWatchdog\releases\<sha>`;
- persistir evidência sanitizada;
- declarar `rdc_required=false`, `production_touched=false` e `secrets_read=false`;
- se Task Scheduler negar `AtStartup + S4U`, retornar `activation_pending=true` e não declarar ativação concluída;
- a ativação headless administrativa deve ocorrer somente por workflow self-hosted fixo no Noteri, sem inputs arbitrários, via UAC legítimo e validação posterior de tarefa `AtStartup + S4U`;
- o workflow de ativação headless não pode executar reboot, produção, shell genérico ou ler segredos.

## Bootstrap físico único

O bootstrap `scripts/activate_noteri_free_control_plane.cmd` deve eliminar a sequência manual de registro sempre que possível:

- localizar e reutilizar runner já registrado sem ler o conteúdo de `.runner`;
- se não existir runner registrado, instalar o GitHub CLI via `winget` quando necessário;
- reutilizar autenticação GitHub CLI válida ou abrir o fluxo oficial `gh auth login --web` quando autenticação humana for inevitável;
- obter o token efêmero de registro pelo endpoint oficial apenas em memória;
- nunca imprimir, persistir ou versionar o token;
- baixar somente o runner oficial Windows x64 pinado pelo código e validar SHA-256 antes de extrair;
- registrar nome `Noteri` e labels adicionais fixos `noteri,reqsys-dev`, usando `--replace` de forma idempotente;
- iniciar o watchdog existente e retornar evidência sanitizada com `rdc_required=false`.

A autenticação interativa do GitHub pode exigir ação humana por consentimento, mas nenhuma etapa recorrente de operação pode voltar a depender do RDC.

## Critérios de aceite de código

- testes unitários do probe/watchdog verdes;
- governance de self-hosted runner verde;
- Gateway continua com allowlist estática;
- workflow sem inputs arbitrários;
- CI do PR verde no SHA atual.

## Critérios de aceite runtime

A rota só fica `runtime_active` após evidência nova de:

1. runner registrado no Noteri com labels fixos, com bootstrap automatizado ou reutilização idempotente;
2. watchdog com tarefa `AtStartup + S4U`, instalada pelo bootstrap elevado governado quando necessário;
3. `Runner.Listener.exe` ativo;
4. comando do Gateway despachando `noteri-control-plane-probe.yml`;
5. workflow saindo de queued/pending e executando no Noteri;
6. artifact mostrando `ok=true`, host Noteri e `rdc_required=false`.
7. em caso negativo sem pickup, o run alvo termina cancelado (ou a falha de cancelamento fica explicitamente registrada), sem fila residual criada pelo Gateway.

Sem esses itens o estado permanece `activation_pending`.


## Ativação headless governada

Quando o runner já estiver ativo, a persistência pré-login deve ser instalada pelo workflow `.github/workflows/noteri-headless-control-plane-activation.yml`, disparado somente pelo comando exato `/reqsys run noteri-headless-control-plane-activation` na issue governada.

O workflow deve:

- executar somente no self-hosted runner `[self-hosted, Windows, X64, noteri, reqsys-dev]`;
- usar checkout do SHA imutável da `main`;
- materializar os scripts do launcher/watchdog desse mesmo SHA em `%LOCALAPPDATA%\\ReqSys\\NoteriControlPlaneBootstrap\\<sha>` antes de criar o atalho interativo;
- validar SHA-256 entre os arquivos do checkout e a cópia materializada;
- o atalho interativo não pode depender de `origin/main`, `FETCH_HEAD` ou de qualquer atualização Git no momento do clique;
- chamar `scripts/noteri_control_plane_watchdog_uac_launcher.py` a partir da cópia imutável materializada;
- usar `ShellExecuteW(..., "runas", ...)` apenas para registrar a tarefa local;
- exigir confirmação fixa `LAUNCH-NOTERI-CONTROL-PLANE-WATCHDOG-UAC`;
- aguardar e validar `exists=true`, trigger de startup e logon `S4U`;
- manter `rdc_required=false`, `production_touched=false` e `reboot_performed=false`;
- persistir artifact sanitizado do staging remoto e não abrir UAC a partir do runner self-hosted;
- o launcher local deve usar o caminho absoluto do Python resolvido no runner no momento do staging, sem depender de `PATH` da sessão do Explorer;
- a execução local deve persistir resultado sanitizado em `%LOCALAPPDATA%\\ReqSys\\NoteriControlPlaneWatchdog\\interactive-launch-result.json`, e a instalação elevada deve manter `elevated-install-result.json`;
- o probe operacional deve consultar a tarefa por `schtasks /Query /XML` sem elevação e publicar `headless_ready`, `exists`, `enabled`, `trigger_at_startup` e `logon_type`, além de diagnóstico sanitizado da última ativação, sem registrar identidade/principal ou segredos.

A autorização do UAC pode exigir clique humano local por regra do Windows; fora esse consentimento, a operação é automatizada.
