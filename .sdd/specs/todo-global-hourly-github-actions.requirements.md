# Requisitos — agendamento do TODO Global no GitHub Actions

## Objetivo

Substituir o agendamento do Work por um ciclo horário versionado no GitHub Actions, sem duplicar a automação e sem expor credenciais.

## Requisitos funcionais

1. O workflow deve executar uma vez por hora e também permitir disparo manual.
2. Cada execução deve gerar `correlation_id` e `event_id` vinculados ao `run_id` e à tentativa do GitHub Actions.
3. A reconciliação deve publicar `todo.reconcile.requested` no Runtime ReqSys.
4. A execução deve aguardar estado terminal com timeout explícito.
5. Sucesso exige `readback_verified=true`.
6. O replay do mesmo evento deve reutilizar o mesmo job e sinalizar duplicidade.
7. Um payload inválido deve ser rejeitado como controle negativo.

## Segurança e operação

- A URL deve ser resolvida pelo locator PC24x7 DEV assinado e usar HTTPS; o consumidor deriva somente o prefixo fixo `/runtime-core`.
- O token de produtor deve ser lido do Azure Key Vault por OIDC, sob nome fixo, sem exposição em log/artifact.
- Ausência de locator, divergência de SHA, token ausente ou runtime indisponível devem falhar antes da publicação do evento.
- Nenhum segredo pode ser escrito em log, artifact ou repositório.
- Falta de configuração, timeout, DLQ, falha ou ausência de leitura independente devem falhar fechado.
- O workflow não executa merge, deploy, alteração administrativa ou produção.

## Critérios de aceite

- YAML válido;
- testes de contrato aprovados;
- Pre-PR Readiness com `READY_FOR_PR=passed` no HEAD exato;
- após materialização do PC24x7 Runtime DEV, run horário terminal no SHA corrente com controle negativo, leitura independente e replay idempotente.
