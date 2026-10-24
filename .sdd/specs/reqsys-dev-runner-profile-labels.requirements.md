# Requisitos — labels de perfil do runner ReqSys DEV

## Contexto

A label compartilhada `reqsys-dev-pool-v1` permitia que um runner preparado somente com
Git e Python capturasse jobs que também exigiam Docker ou Ollama. O pool precisa continuar
portável entre máquinas, mas a seleção física deve respeitar a capacidade comprovada pelo
preflight.

## Critérios de aceite

1. O perfil `base` DEVE exigir somente Git, Python e acesso ao repositório, sem exigir Docker
   ou Ollama.
2. Jobs `base` DEV DEVEM selecionar `reqsys-dev-base-v1` e NÃO DEVEM selecionar labels dos
   perfis `runtime` ou `ollama`.
3. Jobs que exigem Docker DEVEM selecionar `reqsys-dev-runtime-v1`.
4. Jobs que exigem Docker e Ollama DEVEM selecionar `reqsys-dev-ollama-v1`.
5. As labels de runners mais capazes DEVEM ser cumulativas: `runtime` também atende `base`,
   e `ollama` também atende `runtime` e `base`.
6. Cada job portável DEVE executar o preflight governado dentro do próprio bloco de job.
7. O validador DEVE rejeitar uma label de perfil incompatível no mesmo job e DEVE aceitar
   workflows mistos quando identidades fixas aparecem apenas em jobs legados não portáveis.
8. O onboarding DEVE imprimir as labels definidas no perfil selecionado, sem registrar ou
   reconfigurar automaticamente o serviço GitHub Actions.
9. O monitor report-only do pool DEVE medir disponibilidade pelas labels do perfil `base`,
   permitindo que runners `runtime` e `ollama` cumulativos também sejam contabilizados.
10. A mudança DEVE permanecer restrita a DEV e NÃO DEVE habilitar HML, STG ou PROD.
11. Um instalador elevado DEVE configurar o manifesto no `.env` do runner sem
    depender do Registro, validar o perfil antes de aplicar labels, preservar
    labels não gerenciadas e exigir confirmação literal para a mutação no GitHub.
12. O manifesto DEVE ser UTF-8 sem BOM e vincular exatamente perfil,
    capacidades e labels; divergências DEVEM falhar fechadas.
13. O onboarding físico do Noteri DEVE ocorrer somente por comando owner exato,
    SHA atual de `main` e job host-bound; o job NÃO DEVE reiniciar o próprio
    serviço, disparar canário, habilitar retry, fazer deploy ou tocar produção.
14. O onboarding físico do PC24x7 DEVE preparar o perfil `runtime`, comprovando
    Docker antes de reconciliar cumulativamente `reqsys-dev-base-v1` e
    `reqsys-dev-runtime-v1`; a label `ollama` não pode ser aplicada nesse fluxo.

## Evidência esperada

- Testes unitários e de contrato do pool e da governança aprovados.
- `scripts/check_self_hosted_runner_governance.py` com status `pass`.
- `scripts/validate_dev_runtime_cutover.py` com `DEV_RUNTIME_CUTOVER_OK`.
- Preflight local do perfil `base` com status `eligible` em máquina sem Docker.
