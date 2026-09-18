Próximo passo após o merge da PR #1594:

1. Executar o workflow `Integration Excel SQL SharePoint — DEV Readiness` no ambiente GitHub `reqsys-power-platform-dev`.
2. Tratar somente os bloqueios reais apontados por `readiness.json`, sem versionar segredos.
3. Com readiness verde, provisionar/atualizar o fluxo DEV usando `integration_profile_provisioning.py`, mantendo-o parado até a validação do bundle.
4. Executar o E2E real Excel → SQL Server → SharePoint com caso positivo, controle negativo, leitura independente do SharePoint e repetição idempotente.
5. Só declarar o perfil concluído quando as evidências estiverem vinculadas ao mesmo ambiente, SHA e `correlation_id` e não dependerem de cache ou execução anterior.
