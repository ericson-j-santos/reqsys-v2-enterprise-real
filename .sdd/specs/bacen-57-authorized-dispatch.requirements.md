# Disparo governado da avaliação BACEN 57 — Requisitos

## Requisito 1 — comando exato e fechado
O workflow `ReqSys Authorized Actions Gateway` deve aceitar o comando exato `/reqsys run bacen-57-simulation-assessment` somente dentro da allowlist estática já existente.

## Requisito 2 — workflow fixo
O comando deve mapear exclusivamente para `bacen-57-simulation-assessment.yml`, sem aceitar nome de workflow arbitrário, expansão dinâmica ou `eval`.

## Requisito 3 — preservação da fronteira regulatória
O disparo deve permanecer restrito ao workflow de simulação BACEN 57. A mudança não pode alterar a decisão institucional `pending_decision`, liberar produção, ler segredos ou ampliar permissões do gateway.

## Requisito 4 — evidência do disparo
O gateway deve continuar registrando evidência sanitizada com o SHA de `main`, URL/ID da execução disparada, `secrets_read=false` e `production_touched=false`.

## Critérios de aceite (Acceptance Criteria)
1. O comando `/reqsys run bacen-57-simulation-assessment` está explicitamente listado na condição de entrada do gateway.
2. A resolução de rota mapeia o comando exatamente para `bacen-57-simulation-assessment.yml`.
3. A segunda allowlist, imediatamente antes do `gh workflow run`, contém o mesmo workflow fixo.
4. Os três comandos existentes continuam aceitos sem alteração semântica.
5. As permissões permanecem `actions: write` e `contents: read`, sem `contents: write` ou `id-token: write`.
6. O teste `tests/test_reqsys_authorized_actions_gateway.py` cobre o novo comando, o alvo fixo e as salvaguardas NONPROD.
7. O Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato antes da abertura da PR.
