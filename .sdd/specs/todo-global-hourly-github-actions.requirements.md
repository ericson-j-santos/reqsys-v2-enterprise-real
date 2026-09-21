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

- A URL deve vir de `vars.TODO_GLOBAL_RUNTIME_URL` e usar HTTPS.
- O token opcional deve vir de `secrets.TODO_GLOBAL_RUNTIME_TOKEN`.
- Nenhum segredo pode ser escrito em log, artifact ou repositório.
- Falta de configuração, timeout, DLQ, falha ou ausência de leitura independente devem falhar fechado.
- O workflow não executa merge, deploy, alteração administrativa ou produção.

## Critério de aceite

- YAML válido;
- testes de contrato aprovados;
- Pre-PR Readiness com `READY_FOR_PR=passed` no HEAD exato;
- após integração e configuração do ambiente, run horário terminal com controle negativo, leitura independente e replay idempotente.
