# Noteri — fallback independente do plano de controle

## Objetivo

Manter uma rota governada de execução quando o Remote Desktop Commander estiver indisponível ou com cota esgotada, sem usar GUI, mouse, teclado, clipboard ou shell arbitrário.

## Classificação

`gap_fix`.

## Arquitetura

1. O GitHub Authorized Actions Gateway continua como origem externa governada.
2. O runner interativo atual do Noteri permanece operacional com labels fixos `[self-hosted, Windows, X64, noteri, reqsys-dev]` durante a migração.
3. A persistência pré-login é fornecida por um **segundo GitHub Actions Runner oficial**, registrado como serviço Windows pelo próprio `config.cmd --runasservice`, em `C:\actions-runner-noteri-headless`, nome `NoteriHeadless` e labels adicionais `noteri-headless,reqsys-dev`.
4. O runner oficial escolhe a conta de serviço padrão do Windows (NetworkService); nenhum usuário/senha é fornecido pelo ReqSys.
5. O workflow `noteri-control-plane-probe.yml` continua provando o fallback interativo atual.
6. O workflow `noteri-headless-service-probe.yml` prova pickup real pelo runner `NoteriHeadless`, host exato e `Runner.Listener.exe`, sem depender de RDC.
7. O Gateway aceita somente comandos exatos allowlisted e falha fechado quando um runner self-hosted não adquire o job.
8. Runs sem pickup são cancelados por ID exato, com evidência do cleanup e sem retry automático.

## Decisão arquitetural — S4U não é runtime headless válido

A tarefa `AtStartup + S4U` deixa de ser critério de aceite. O logon S4U do Task Scheduler não fornece acesso à rede; portanto não satisfaz o requisito funcional de um GitHub Actions Runner, que precisa comunicar-se com o GitHub.

O código legado de watchdog pode continuar existindo temporariamente para compatibilidade do fallback interativo, mas:
- não comprova persistência headless;
- não libera `runtime_active` do runner headless;
- não deve ser usado como substituto do serviço nativo do GitHub Runner.

## Requisitos

- executar somente no host exato `Noteri`;
- local/DEV somente;
- não ler conteúdo de `.runner`;
- token de registro efêmero pode ser consumido somente em memória; é proibido imprimir, persistir, versionar ou incluí-lo na evidência;
- não executar reboot/shutdown;
- não expor comando arbitrário;
- usar runner oficial Windows x64 pinado e validar SHA-256 antes da extração;
- usar diretório dedicado `C:\actions-runner-noteri-headless`;
- usar nome fixo `NoteriHeadless` e labels `noteri-headless,reqsys-dev`;
- usar `config.cmd --runasservice`; não criar serviço manual paralelo;
- não fornecer `windowslogonpassword` ou segredo de conta de serviço;
- exigir elevação administrativa somente para o provisionamento inicial do serviço;
- manter o runner interativo atual intacto até o E2E do `NoteriHeadless` ficar verde;
- persistir apenas evidência sanitizada;
- declarar `rdc_required=false`, `production_touched=false` e `secrets_read=false`;
- status sem mutação deve validar o marcador `.service`, existência do serviço no SCM, auto-start e estado Running;
- nenhuma alteração de produção, deploy ou reboot faz parte deste incremento.

## Bootstrap físico único

O bootstrap `scripts/activate_noteri_free_control_plane.py` deve:

- preservar o modo interativo existente;
- oferecer `--mode headless-service` para provisionar o runner dedicado como serviço;
- oferecer `--mode headless-service-status` para validação somente leitura;
- baixar somente o runner oficial pinado e validar SHA-256;
- obter o token efêmero pelo endpoint oficial somente em memória;
- registrar `NoteriHeadless` por `config.cmd --runasservice`;
- deixar o próprio runner oficial selecionar NetworkService como conta padrão;
- falhar fechado se o diretório dedicado já estiver registrado sem `.service`;
- validar serviço pelo Windows Service Control Manager;
- nunca imprimir token, senha ou credencial.

O workflow `.github/workflows/noteri-headless-control-plane-activation.yml` materializa `Ativar-Noteri-Headless.cmd/.ps1` no Desktop. O launcher eleva somente via `Start-Process -Verb RunAs`; após a elevação, executa o bootstrap fixo. Não há bypass de UAC.

## Critérios de aceite de código

- testes do probe/bootstrap verdes;
- governance de self-hosted runner verde;
- Gateway continua com allowlist estática;
- workflows sem inputs arbitrários;
- S4U ausente do workflow de ativação headless;
- senha de conta de serviço ausente;
- Pre-PR Readiness `READY_FOR_PR=passed` no HEAD exato antes de abrir PR.

## Critérios de aceite runtime

A persistência headless só fica comprovada após evidência nova, no mesmo SHA, de:

1. runner interativo atual continua funcional durante a migração;
2. `NoteriHeadless` registrado em `C:\actions-runner-noteri-headless`;
3. marcador `.service` válido;
4. serviço Windows existente, configurado para auto-start e Running;
5. runner com labels `[self-hosted, Windows, X64, noteri-headless, reqsys-dev]`;
6. Gateway despacha `noteri-headless-service-probe.yml`;
7. workflow sai de queued/pending e executa em `RUNNER_NAME=NoteriHeadless`;
8. artifact mostra `ok=true`, host Noteri, `runner_listener_detected=true` e `rdc_required=false`;
9. replay do probe não cria outro runner nem altera configuração;
10. controle negativo de nome de runner divergente falha fechado.

Sem esses itens, o estado permanece `activation_pending`.

## Ativação headless governada

A ativação administrativa continua sendo disparada pelo comando exato `/reqsys run noteri-headless-control-plane-activation` na issue governada. O workflow roda no runner interativo atual, materializa o launcher local e valida o serviço sem mutação.

Depois do único consentimento UAC local, a prova independente deve usar o comando exato `/reqsys run noteri-headless-service-probe`.

Nenhum merge, deploy, reboot, produção, shell genérico ou leitura de segredo é autorizado por este fluxo.
