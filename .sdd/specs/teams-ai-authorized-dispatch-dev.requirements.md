# Disparo governado Teams IA DEV — Requisitos

## Requisito 1 — comandos exatos e fechados
O workflow `ReqSys Authorized Actions Gateway` deve aceitar somente os comandos exatos `/reqsys run pc24x7-teams-token-bootstrap-dev` e `/reqsys run pc24x7-teams-e2e-dev`, mantendo a restrição à issue #1705 e ao ator autorizado já existente.

## Requisito 2 — workflows fixos
Os comandos devem mapear exclusivamente para `pc24x7-teams-token-bootstrap.yml` e `pc24x7-teams-ephemeral-e2e.yml`, sem aceitar nome de workflow, branch ou parâmetro arbitrário.

## Requisito 3 — DEV apenas
A ampliação deve permanecer restrita ao contrato DEV já codificado nos workflows alvo. O gateway não pode adicionar inputs de HML/STG/PROD, promover ambiente, executar deploy de produção ou ampliar permissões.

## Requisito 4 — menor privilégio
As permissões do gateway permanecem `actions: write` e `contents: read`, sem `contents: write`, `id-token: write` ou leitura de secrets. A autenticação OIDC e os segredos necessários continuam pertencendo aos workflows alvo e seus environments governados.

## Requisito 5 — evidência vinculada ao run exato
O gateway deve capturar o SHA corrente de `main`, usar o URL/ID devolvido por `gh workflow run`, reler esse run e falhar fechado se ID, URL, SHA ou evento divergirem. A evidência sanitizada deve manter `secrets_read=false` e `production_touched=false`.

## Requisito 6 — sequência operacional
Após integração desta mudança, a sequência autorizada para a issue #1532 é:
1. disparar `pc24x7-teams-token-bootstrap-dev`;
2. exigir estado READY do token S2S com escopo `teams_gateway:ai_conversations`;
3. disparar `pc24x7-teams-e2e-dev`;
4. exigir readiness DEV, Teams real, mesmo `conversation_id`, idempotência por `activity.id`, correlação, SHA-256, auditoria e revogação do token efêmero;
5. manter TEST/HML/PROD intocados.

## Critérios de aceite
1. Ambos os comandos constam na condição de entrada do gateway.
2. Ambos os comandos têm roteamento estático para os workflows corretos.
3. Ambos os workflows constam na segunda allowlist antes do `gh workflow run`.
4. Não há `eval`, nome de workflow arbitrário ou inputs de ambiente produtivo.
5. As permissões do gateway permanecem mínimas.
6. `tests/test_reqsys_authorized_actions_gateway.py` cobre os dois novos comandos, targets e fronteira NONPROD.
7. O Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato, com `behind_by=0`, antes da abertura da PR.
