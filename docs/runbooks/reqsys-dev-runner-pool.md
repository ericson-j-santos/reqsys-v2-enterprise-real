# Pool compartilhado de runners ReqSys DEV

O pool `reqsys-dev-pc-pool-v1` permite que qualquer PC Windows x64 preparado assuma os jobs DEV. Nome da máquina e `runner_id` não são identidade nem critério de elegibilidade.

## Onboarding

1. Instale Git, Python e, para o perfil `runtime`, Docker. O perfil `ollama` também exige Ollama.
2. Crie um diretório absoluto e exclusivo para o runtime DEV. Não use links/reparse points nem caminhos contendo `hml`, `stg`, `prod` ou `production`.
3. Em PowerShell elevado, execute:

   `./scripts/onboard_reqsys_dev_runner.ps1 -RunnerInstanceId reqsys-pc-<id-estavel> -RuntimeRoot <diretorio> -Profile runtime`

4. Configure `REQSYS_DEV_RUNNER_MANIFEST` no serviço do GitHub Actions com o caminho do manifesto gerado.
5. Somente depois do preflight positivo, associe as labels impressas pelo script: `self-hosted`, `Windows`, `X64`, `reqsys-dev`, `reqsys-dev-pool-v1`.

O manifesto é local e não contém segredo. `runner_instance_id` deve ser um identificador opaco e estável; hostname e id numérico do GitHub são proibidos. Cada job executa novamente o preflight e falha fechado se ferramenta, checkout, runtime root, escopo DEV ou salvaguarda divergir.

## Retirada e validação

Remova primeiro `reqsys-dev-pool-v1` no GitHub para drenar o PC. Não apague o manifesto nem altere serviços enquanto houver job ativo. Para revalidar sem reescrever o manifesto, use `-ValidateOnly` e o mesmo conjunto de parâmetros.

O pool não autoriza dispatch, retry, deploy ou promoção. HML, STG e PROD permanecem bloqueados; concurrency dos workflows continua sendo o mecanismo de serialização do domínio.

## Fases de adoção

- Fase 1 (esta PR): contrato central, preflight, onboarding, canário próprio do pool, gateway governado e fluxos portáveis de reconcile/Ollama/Figma/Teams/TODO/handoff.
- Fase 2: migrar os diagnósticos sintéticos e inventários históricos do Worker Pool que ainda usam a label legada `pc24x7`.
- Fase 3: revisar cada workflow de recuperação de equipamento. Somente ações cujo alvo seja realmente o equipamento permanecem host-bound; ações portáveis são movidas ao pool.
- Fase 4: onboarding físico gradual, drenagem da label legada e um único canário DEV por autorização owner específica.

As fases 2–4 não são autorizadas por esta PR. Em especial, a Fase 4 exige mudança operacional separada e não pode ocorrer por retry automático.
