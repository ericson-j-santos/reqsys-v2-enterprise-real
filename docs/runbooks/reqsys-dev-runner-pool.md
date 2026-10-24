# Pool compartilhado de runners ReqSys DEV

O pool `reqsys-dev-pc-pool-v1` permite que qualquer PC Windows x64 preparado assuma os jobs DEV. Nome da máquina e `runner_id` não são identidade nem critério de elegibilidade.

## Onboarding

1. Instale Git e Python para o perfil `base`. O perfil `runtime` também exige Docker; o perfil `ollama` exige Docker e Ollama.
2. Crie um diretório absoluto e exclusivo para o runtime DEV. Não use links/reparse points nem caminhos contendo `hml`, `stg`, `prod` ou `production`.
3. Em PowerShell elevado, execute:

   `./scripts/onboard_reqsys_dev_runner.ps1 -RunnerInstanceId reqsys-pc-<id-estavel> -RuntimeRoot <diretorio> -Profile base`

4. Configure `REQSYS_DEV_RUNNER_MANIFEST` no serviço do GitHub Actions com o caminho do manifesto gerado.
5. Somente depois do preflight positivo, associe as labels impressas pelo script. O perfil `base` recebe `reqsys-dev-base-v1`; `runtime` recebe também `reqsys-dev-runtime-v1`; `ollama` recebe também `reqsys-dev-ollama-v1`.

O manifesto é local e não contém segredo. `runner_instance_id` deve ser um identificador opaco e estável; hostname e id numérico do GitHub são proibidos. Cada job executa novamente o preflight e falha fechado se ferramenta, checkout, runtime root, escopo DEV ou salvaguarda divergir.

## Retirada e validação

Remova primeiro a label mais especializada (`ollama`, depois `runtime`, depois `base`) no GitHub para drenar o PC. Não apague o manifesto nem altere serviços enquanto houver job ativo. Para revalidar sem reescrever o manifesto, use `-ValidateOnly` e o mesmo conjunto de parâmetros.

## Monitoramento

O workflow canônico `Self-Hosted Runner Governance Guard` executa o monitor do pool a cada 30 minutos e também pode ser disparado manualmente. Ele compara o inventário de runners com as labels da política versionada, exige pelo menos dois runners elegíveis online e publica somente evidência sanitizada. O monitor é report-only: não adiciona labels, não reinicia máquinas, não faz deploy e não toca produção.

O pool não autoriza dispatch, retry, deploy ou promoção. HML, STG e PROD permanecem bloqueados; concurrency dos workflows continua sendo o mecanismo de serialização do domínio.

## Fases de adoção

- Fase 1 (esta PR): contrato central, preflight, onboarding, canário próprio do pool, gateway governado e fluxos portáveis de reconcile/Ollama/Figma/Teams/TODO/handoff.
- Fase 2: migrar os diagnósticos sintéticos e inventários históricos do Worker Pool que ainda usam a label legada `pc24x7`.
- Fase 3: revisar cada workflow de recuperação de equipamento. Somente ações cujo alvo seja realmente o equipamento permanecem host-bound; ações portáveis são movidas ao pool.
- Fase 4: onboarding físico gradual, drenagem da label legada e um único canário DEV por autorização owner específica.

As fases 2–4 não são autorizadas por esta PR. Em especial, a Fase 4 exige mudança operacional separada e não pode ocorrer por retry automático.
