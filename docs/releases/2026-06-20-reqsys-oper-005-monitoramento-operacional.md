# 2026-06-20 — REQSYS-OPER-005 — Monitoramento operacional

## Resumo

Incremento inicial para implementar o endpoint `/monitoramento-operacional` no backend do ReqSys.

## Alterações

- Adicionado router `backend/app/api/monitoramento_operacional.py`.
- Registrado router no `backend/app/main.py`.
- Adicionados testes automatizados para contrato mínimo, envelope, correlação, classificador de estado e ausência de campos sensíveis.

## Contrato inicial

O endpoint retorna envelope padrão da API contendo:

- `schema_version`;
- `correlation_id`;
- `coletado_em`;
- `ambiente`;
- `resumo`;
- `itens`.

## Regras implementadas

- Estado geral prioriza `bloqueado`.
- Lista vazia retorna `desconhecido`.
- PR ou incremento em andamento não é classificado como pronto para merge.
- Resposta inicial não expõe credenciais, segredos ou dados pessoais.

## Próximos incrementos

- Conectar coleta real de PRs e GitHub Actions.
- Publicar artifact `pipeline-governanca-report` no CI.
- Criar painel frontend com cards e drill-down analítico.
- Persistir histórico de snapshots operacionais.

Refs #46
Refs #33
