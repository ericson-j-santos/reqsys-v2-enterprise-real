# PC24x7 — reparo governado do registro do runner

## Objetivo

Diagnosticar e corrigir, sem executar shell no Desktop, divergências de labels do runner GitHub Actions `DESKTOP-PDQK954`.

## Requisitos

1. Executar somente em GitHub-hosted runner `ubuntu-latest`.
2. Consultar somente o repositório `ericson-j-santos/reqsys-v2-enterprise-real`.
3. Selecionar somente o runner de nome exato `DESKTOP-PDQK954`.
4. Falhar fechado se o runner estiver ausente, duplicado ou `offline`.
5. Quando o runner estiver `online`, alterar somente as labels customizadas para `pc24x7` e `reqsys-dev`.
6. Exigir ao final as labels `self-hosted`, `Windows`, `X64`, `pc24x7` e `reqsys-dev`.
7. Nunca imprimir, persistir ou publicar o token GitHub.
8. Não executar comando, shell, reboot, deploy ou acesso a segredo no Desktop.
9. Publicar artifact sanitizado com estado, busy, labels antes/depois e indicador de mutação.
10. O Authorized Actions Gateway aceita somente `/reqsys run pc24x7-runner-registry-repair`, sem inputs.

## Critérios de aceite

- `runner_missing` quando o registro exato não existe.
- `runner_offline` quando existe mas está offline.
- `runner_labels_mismatch` quando as labels obrigatórias ainda não convergem.
- `runner_registry_ready` somente com status online e labels completas.
- Após `runner_registry_ready`, a prova terminal continua sendo pickup real de workflow PC24x7.
