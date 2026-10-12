# Desktop GitHub Runner — bootstrap governado e pickup físico

## Objetivo

Recuperar o runner GitHub Actions já registrado no `DESKTOP-PDQK954` usando o Engineering Orchestrator ativo em DEV, sem shell remoto, GUI, token, reboot ou intervenção humana, e comprovar pickup físico independente pelo GitHub.

## Contrato

1. A origem do bootstrap é exclusivamente o host `Noteri`.
2. O destino é fixo em `DESKTOP-PDQK954:8787`.
3. Antes da mutação, exigir worker `desktop-pdqk954` fresco, elegível, controller >= `0.2.53` e `recovery_contract_version=1`. Se `host.github_runner.bootstrap.v1` ainda não estiver anunciado ou a identidade do runtime não corresponder ao alvo, exigir `host.orchestrator.refresh.v1`, despachar refresh governado e pinado ao SHA `313f5da4bb0ee9dd70937c238c7cfdf4e3514602`, e só aceitar o refresh após readback independente de `runtime_source_sha` igual ao SHA alvo, `worker_instance_id` válido e diferente da instância anterior quando disponível, e `host.github_runner.bootstrap.v1` presente.
4. O payload enviado ao Orchestrator contém somente `target_host=DESKTOP-PDQK954`; não aceita caminho, comando, URL, token ou segredo.
5. O item usa risco 2, uma tentativa e timeout finito.
6. Sucesso local exige estado `CONCLUÍDO`, handler/host/worker exatos, `local_listener_verified=true`, `pickup_required=true`, `github_connectivity_verified=false`, `production_touched=false` e `secrets_read=false`.
7. Repetir o mesmo evento deve retornar `replayed=true`, o mesmo work item e nenhuma nova dispatch.
8. O bootstrap local nunca é evidência terminal de conectividade GitHub.
9. A prova terminal é um workflow separado adquirido pelo runner exato `DESKTOP-PDQK954`, no SHA exato da execução.
10. O canário não toca produção, não lê segredos e valida host, runner, repositório e SHA.
11. Ambos os workflows usam Session Launcher e Command Gateway com regras canônicas em SHA imutável.
12. O Authorized Actions Gateway aceita somente:
    - `/reqsys run desktop-runner-bootstrap-via-orchestrator`;
    - `/reqsys run desktop-runner-pickup-canary`.
13. Nenhum input arbitrário é aceito por esses dois comandos.
14. O arquivo de evidência do bootstrap deve ser gravado em `RUNNER_TEMP`, fora do worktree validado pelo Command Gateway, para que observabilidade não produza falso `state_changed`.
15. A concorrência do workflow deve ser serial por `mode` e usar `cancel-in-progress: false`; um comando duplicado pode permanecer enfileirado ou ser cancelado pelo gateway por ausência de pickup, mas nunca pode cancelar uma recuperação do mesmo modo que já esteja em execução.
16. O job `runner-bootstrap` deve reservar 12 minutos para cobrir checkout, download e validação do Python portátil e a execução governada; os limites internos permanecem restritos a 150 segundos no Command Gateway e 90 segundos no bootstrap do Orchestrator.
17. O job `runner-canary` deve fixar regras f6ccb143a581e28650e9b640226f9ef671d469f2 (suporte ao checkout transitório `GITHUB_WORKSPACE` com remoto/HEAD comprovados), criar sessão/worktree isolado e falhar fechado se a origem ou política divergir; os demais modos permanecem inalterados.

18. O mesmo canário pode anexar uma leitura **somente observacional** de CPU lógico, RAM total/disponível, espaço total/livre do disco do sistema, contagem de instâncias SQL no registro e presença do executável Docker. Essa leitura usa apenas Python stdlib, Win32 API e registro somente leitura, não inicia processos externos nem invoca Docker, PowerShell, serviços ou comandos SQL.
19. O snapshot deve diferenciar `status=measured` de `status=unavailable`. Uma falha do inventário nunca transforma pickup verdadeiro em aprovação HML e nunca revela detalhes de exceção. Nenhuma métrica individual comprova SQL ativo, Docker daemon, autorização de provisionamento, isolamento de recursos ou prontidão HML.
20. O escopo continua restrito ao runner `DESKTOP-PDQK954` e ao SHA/repositório exatos. Host incorreto deve ser rejeitado antes da coleta. Nenhum novo workflow, modo de dispatch, configuração de host, serviço, credencial, banco ou recurso de produção é criado/modificado.

## Critérios de aceite

O fluxo só é concluído quando houver evidência atual e vinculada ao mesmo ciclo operacional de:

`Noteri -> Orchestrator :8787 -> refresh governado quando necessário -> readback de runtime_source_sha + nova worker_instance_id + host.github_runner.bootstrap.v1 -> bootstrap do runner -> listener local verificado -> GitHub Actions -> pickup no DESKTOP-PDQK954 -> canário concluído no SHA exato`.

Para decidir sobre instalação de um HML próprio, exigir também medição física `capacity.status=measured`, prova separada de serviços/contêineres em funcionamento, isolamento e autorização específica. A nova telemetria não autoriza a instalação por si só.

Listener local sem pickup mantém o estado parcial.
