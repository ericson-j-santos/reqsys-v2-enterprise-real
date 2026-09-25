# Desktop GitHub Runner — bootstrap governado e pickup físico

## Objetivo

Recuperar o runner GitHub Actions já registrado no `DESKTOP-PDQK954` usando o Engineering Orchestrator ativo em DEV, sem shell remoto, GUI, token, reboot ou intervenção humana, e comprovar pickup físico independente pelo GitHub.

## Contrato

1. A origem do bootstrap é exclusivamente o host `Noteri`.
2. O destino é fixo em `DESKTOP-PDQK954:8787`.
3. Antes da mutação, exigir worker `desktop-pdqk954` fresco, elegível, controller >= `0.2.53` e `recovery_contract_version=1`. Se `host.github_runner.bootstrap.v1` ainda não estiver anunciado, exigir `host.orchestrator.refresh.v1`, despachar refresh governado e pinado ao SHA `4dbc927595a40fc2fd6b207c0d53fd6e895049ae`, e comprovar por readback que `bootstrap.v1` passou a existir antes de prosseguir.
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

## Critérios de aceite

O fluxo só é concluído quando houver evidência atual e vinculada ao mesmo ciclo operacional de:

`Noteri -> Orchestrator :8787 -> refresh governado quando necessário -> readback de host.github_runner.bootstrap.v1 -> bootstrap do runner -> listener local verificado -> GitHub Actions -> pickup no DESKTOP-PDQK954 -> canário concluído no SHA exato`.

Listener local sem pickup mantém o estado parcial.
