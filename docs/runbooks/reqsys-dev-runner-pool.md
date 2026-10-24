# Pool compartilhado de runners ReqSys DEV

O pool `reqsys-dev-pc-pool-v1` permite que qualquer PC Windows x64 preparado assuma os jobs DEV. Nome da máquina e `runner_id` não são identidade nem critério de elegibilidade.

## Onboarding

1. Instale Git, Python e, para o perfil `runtime`, Docker. O perfil `ollama` também exige Ollama.
2. Crie um diretório absoluto e exclusivo para o runtime DEV. Não use links/reparse points nem caminhos contendo `hml`, `stg`, `prod` ou `production`.
3. Em PowerShell elevado, execute o instalador idempotente. Ele cria o manifesto em UTF-8 sem BOM, valida o perfil, configura a `.env` do runner e, quando solicitado explicitamente, reinicia uma única vez o serviço informado:

   `./scripts/install_reqsys_dev_runner.ps1 -RunnerInstanceId reqsys-pc-<id-estavel> -RuntimeRoot C:\ReqSysDev\Runtime -RunnerRoot C:\actions-runner -Profile base -RunnerServiceName actions.runner.exemplo.reqsys -RestartRunnerService -ApplyGitHubLabels -Confirm APPLY-REQSYS-DEV-RUNNER-LABELS`

4. Com `-ApplyGitHubLabels`, o instalador usa o `agentId` do arquivo local `.runner`, preserva labels customizadas não gerenciadas (como `noteri`) e reconcilia via `gh api` somente as labels do pool após o preflight. O perfil `base` recebe `reqsys-cap-base-v1`; `runtime` recebe também `reqsys-cap-runtime-v1`; `ollama` recebe também `reqsys-cap-ollama-v1`.
5. Nunca associe manualmente uma label de capacidade superior àquela materializada no manifesto. Os workflows exigem a label antes do pickup e repetem o preflight após o checkout.

O manifesto é local e não contém segredo. `runner_instance_id` deve ser um identificador opaco e estável; hostname e id numérico do GitHub são proibidos. Cada job executa novamente o preflight e falha fechado se ferramenta, checkout, runtime root, escopo DEV ou salvaguarda divergir.

## Retirada e validação

Remova primeiro a label de capacidade mais alta e depois `reqsys-dev-pool-v1` no GitHub para drenar o PC. Não apague o manifesto nem altere serviços enquanto houver job ativo. Para revalidar sem reescrever o manifesto, use `onboard_reqsys_dev_runner.ps1 -ValidateOnly` e o mesmo conjunto de parâmetros.

O pool não autoriza dispatch, retry, deploy ou promoção. HML, STG e PROD permanecem bloqueados; concurrency dos workflows continua sendo o mecanismo de serialização do domínio.

## Fases de adoção

- Fase 1 (esta PR): contrato central, preflight, onboarding, canário próprio do pool, gateway governado e fluxos portáveis de reconcile/Ollama/Figma/Teams/TODO/handoff.
- Fase 2: migrar os diagnósticos sintéticos e inventários históricos do Worker Pool que ainda usam a label legada `pc24x7`.
- Fase 3: revisar cada workflow de recuperação de equipamento. Somente ações cujo alvo seja realmente o equipamento permanecem host-bound; ações portáveis são movidas ao pool.
- Fase 4: onboarding físico gradual, drenagem da label legada e um único canário DEV por autorização owner específica.

As fases 2–4 não são autorizadas por esta PR. Em especial, a Fase 4 exige mudança operacional separada e não pode ocorrer por retry automático.
