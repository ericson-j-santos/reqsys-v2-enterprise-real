# Pool compartilhado de runners ReqSys DEV

O pool `reqsys-dev-pc-pool-v1` permite que qualquer PC Windows x64 preparado assuma os jobs DEV. Nome da máquina e `runner_id` não são identidade nem critério de elegibilidade.

## Onboarding

1. Instale Git e Python para o perfil `base`. O perfil `runtime` também exige Docker; o perfil `ollama` exige Docker e Ollama.
2. Crie um diretório absoluto e exclusivo para o runtime DEV. Não use links/reparse points nem caminhos contendo `hml`, `stg`, `prod` ou `production`.
3. Em PowerShell elevado, a partir da raiz do repositório, execute o instalador
   com caminhos reais. Não copie marcadores entre `<` e `>` para o PowerShell;
   eles são apenas placeholders de documentação. Exemplo mínimo para um runner
   já instalado em `C:\actions-runner`:

   `& ".\scripts\install_reqsys_dev_runner.ps1" -RunnerInstanceId "reqsys-pc-7f3a91c2" -RuntimeRoot "C:\ReqSysDev\Runtime" -RunnerRoot "C:\actions-runner" -Profile base`

4. O instalador grava `REQSYS_DEV_RUNNER_MANIFEST` no arquivo `.env` do runner,
   em UTF-8 sem BOM, sem depender de permissão de escrita no Registro. Para
   reiniciar exatamente um serviço `actions.runner.*`, acrescente
   `-RestartRunnerService`; se houver mais de um serviço, informe também
   `-RunnerServiceName` e o nome exato.
5. Somente depois do preflight positivo, aplique as labels com
   `-ApplyGitHubLabels -Confirm APPLY-REQSYS-DEV-RUNNER-LABELS`. O perfil `base`
   recebe `reqsys-dev-base-v1`; `runtime` recebe também
   `reqsys-dev-runtime-v1`; `ollama` recebe também `reqsys-dev-ollama-v1`.
   Labels customizadas não gerenciadas, como uma label operacional local, são
   preservadas. O instalador obtém o `runner_id` do arquivo `.runner`; ele não
   aceita um ID fixo como parâmetro.

O manifesto é local e não contém segredo. `runner_instance_id` deve ser um identificador opaco e estável; hostname e id numérico do GitHub são proibidos. Cada job executa novamente o preflight e falha fechado se ferramenta, checkout, runtime root, perfil, labels, escopo DEV ou salvaguarda divergir.

### Segundo PC já registrado

Quando um PC Windows x64 já registrado responde pela capacidade bootstrap `pc24x7`, o owner pode usar os comandos exatos `/reqsys run pc24x7-runner-pool-onboard` e, somente depois do retorno online e da evidência positiva, `/reqsys run pc24x7-runner-pool-label-reconcile`. O primeiro comando cria ou atualiza apenas o manifesto DEV e o `.env` do runner, valida o perfil `base`, publica evidência sanitizada e agenda uma única reinicialização atrasada do listener. O segundo roda hospedado, consome a evidência exata e aplica a label compartilhada sem transportar credencial administrativa ao PC.

Esse bootstrap seleciona a capacidade `pc24x7`; não compara hostname, não recebe `runner_id`, não executa canário e não habilita HML, STG ou PROD. Se a máquina não voltar online ou o readback falhar, a reconciliação deve parar sem retry automático.

A etapa privilegiada não executa o instalador diretamente no token do serviço do runner. Ela exige a tarefa local preexistente `\Automation\ReqSysDesktopAdminBroker` com trigger `AtStartup`, logon `S4U`, nível `highest` e estado habilitado. O job apenas prepara uma release vinculada ao SHA e reinicia essa tarefa; nenhum usuário, senha, PAT ou segredo administrativo é fornecido. O broker elevado busca novamente o comentário owner exato na issue operacional, revalida idade, SHA, origem e limpeza do checkout, raiz e marcador do serviço do runner, aplica somente o perfil `base`/DEV e agenda uma única reinicialização atrasada. Qualquer divergência bloqueia o fluxo sem retry.

O registro S4U na API COM do Windows utiliza senha nula (`None`), nunca string vazia. O preflight de reconciliação do perfil `base` no PC24x7 exige evidência da tarefa administrativa, do agendamento do restart e da identidade da instância; sem esses dados, não aplica labels.

Quando o serviço do runner não executa elevado, o perfil `runtime` usa uma rota separada que não tenta contornar UAC: `/reqsys run pc24x7-runner-pool-runtime-onboard`. Ela grava apenas `%LOCALAPPDATA%\ReqSys\runner-pool.json` e o runtime root fixo no mesmo escopo de usuário, recusa reparse points em toda a cadeia, localiza exatamente um registro do runner entre os ancestrais de `GITHUB_WORKSPACE`, exige Docker CLI e Docker Engine local por named pipe Windows allowlisted e publica somente evidência sanitizada. Quando o manifesto local existe, os preflights `base` e `runtime` o preferem ao caminho legado de `REQSYS_DEV_RUNNER_MANIFEST`; um manifesto `runtime` satisfaz `base`, mas o inverso falha fechado. `ollama` e runners sem esse arquivo preservam a resolução anterior. Assim, a rota não altera `.env`, não reinicia nem enumera globalmente serviços do listener.

Após o workflow físico terminar e o runner estar online e ocioso, o owner pode emitir `/reqsys run pc24x7-runner-pool-runtime-label-reconcile`. A reconciliação hospedada consome o artifact runtime exato, preserva labels não gerenciadas, aplica cumulativamente `reqsys-dev-base-v1` e `reqsys-dev-runtime-v1` e exige readback independente ainda online e ocioso. Tanto o onboarding quanto a reconciliação rejeitam dispatch de colaborador: apenas o owner ou o gateway como `github-actions[bot]` podem combinar o comentário owner exato com o SHA atual. A reconciliação permanece bloqueada até a GitHub App `REQSYS_STACK_REBASE` ter, na instalação deste repositório, `Administration: Read and write` e `Actions: Read-only`; ausência de permissão não permite fallback para PAT ou `GITHUB_TOKEN`.

## Retirada e validação

Remova primeiro a label mais especializada (`ollama`, depois `runtime`, depois `base`) no GitHub para drenar o PC. Não apague o manifesto nem altere serviços enquanto houver job ativo. Para revalidar sem reescrever o manifesto, execute `onboard_reqsys_dev_runner.ps1` com `-ValidateOnly` e o mesmo conjunto de parâmetros.

## Monitoramento

O workflow canônico `Self-Hosted Runner Governance Guard` executa o monitor do pool a cada 30 minutos e também pode ser disparado manualmente. Ele envia simultaneamente dois leases efêmeros pelas labels portáteis do perfil `base`; cada PC executa o preflight e mantém o lease observável por 75 segundos. Um observador GitHub-hosted lê apenas os jobs da própria execução com `github.token` e `actions: read`, exige duas conclusões positivas em runners distintos e publica somente evidência sanitizada. Um único PC que execute os slots em sequência não satisfaz o requisito de capacidade dois.

Esse desenho não consulta o endpoint administrativo de inventário, não usa PAT pessoal, não solicita `administration: read` e não depende de credencial armazenada em qualquer PC. Como as labels são cumulativas, runners `runtime` e `ollama` também podem atender o perfil `base`. Cada slot tem concurrency própria com cancelamento da medição anterior, limitando leases que permaneçam na fila quando não houver capacidade. O monitor é report-only: não adiciona labels, não reinicia máquinas, não faz deploy e não toca produção.

Se os leases não comprovarem dois runners distintos elegíveis, a evidência é publicada com `status=degraded` e o job de auditoria falha. A falha é deliberada para impedir falso verde operacional; ela não dispara retry, reconciliação, deploy ou qualquer mutação automática.

Fora desses dois leases internos, o pool não autoriza dispatch arbitrário, retry, deploy ou promoção. HML, STG e PROD permanecem bloqueados; concurrency dos workflows continua sendo o mecanismo de serialização do domínio.

## Fases de adoção

- Fase 1 (esta PR): contrato central, preflight, onboarding, canário próprio do pool, gateway governado e fluxos portáveis de reconcile/Ollama/Figma/Teams/TODO/handoff.
- Fase 2: migrar os diagnósticos sintéticos e inventários históricos do Worker Pool que ainda usam a label legada `pc24x7`.
- Fase 3: revisar cada workflow de recuperação de equipamento. Somente ações cujo alvo seja realmente o equipamento permanecem host-bound; ações portáveis são movidas ao pool.
- Fase 4: onboarding físico gradual, drenagem da label legada e um único canário DEV por autorização owner específica.

As fases 2–4 não são autorizadas por esta PR. Em especial, a Fase 4 exige mudança operacional separada e não pode ocorrer por retry automático.
