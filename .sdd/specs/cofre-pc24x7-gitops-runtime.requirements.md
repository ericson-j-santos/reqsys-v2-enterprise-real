# Cofre DEV PC24x7 — consolidação GitOps

## Objetivo
Eliminar o drift entre o runtime DEV PC24x7 validado e a configuração versionada, preservando o valor da passphrase fora do Git.

## Requisitos
1. O overlay versionado deve montar a passphrase a partir de arquivo protegido do host e nunca conter o valor do segredo.
2. O mount deve chegar ao container em `/run/secrets/cofre_keyring_passphrase`.
3. O processo da API deve exportar `COFRE_KEYRING_PASSPHRASE` somente em runtime a partir do arquivo montado.
4. O Cofre deve usar `REQSYS_DATA_DIR=/data`.
5. `/data` deve usar volume persistente `reqsys-cofre-data`.
6. O executor E2E deve continuar limitado a DEV, validar SHA do runtime, persistência após restart, controle negativo de escopo, auditoria e cleanup.
7. Nenhuma alteração em HML/STG/PROD faz parte deste incremento.

## Critérios de aceite
1. Testes do contrato GitOps passam no SHA exato da branch.
2. `docker compose config` com o overlay versionado é válido sem revelar o valor da passphrase.
3. O Pre-PR Readiness termina `passed`, com `behind_by=0`, SDD válido e sem blockers.
4. Uma PR é aberta vinculando #1760 e a issue de infraestrutura #1, sem merge automático.
5. A API DEV é recriada usando o overlay versionado.
6. Após recreate, o container fica `healthy`, mantém o mount somente leitura e o volume persistente.
7. O E2E real do Cofre após recreate comprova persistência, auditoria, controles negativos e cleanup.
8. `sensitive_values_exposed=false` e `production_touched=false`.
