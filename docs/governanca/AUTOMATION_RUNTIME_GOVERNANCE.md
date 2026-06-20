# Automation Runtime Governance

## Objetivo

Padronizar a governanca de automacoes criticas do ReqSys.

## Principio

Automacao ativa nao significa automacao entregue.

## Regra

Uma automacao somente pode ser considerada operacional quando houver evidencia de execucao, geracao de artefato, entrega, confirmacao e registro de resultado.

## Estados

- scheduled
- enabled
- running
- generated
- delivery_requested
- delivered
- delivery_confirmed
- retrying
- failed
- blocked
- unknown

## Checklist minimo

- agendamento cadastrado;
- frequencia definida;
- execucao iniciada;
- correlation_id gerado;
- artefato gerado;
- entrega solicitada;
- entrega confirmada;
- retry registrado;
- falha classificada;
- resumo executivo produzido.

## Regras de bloqueio

Bloquear quando faltar canal, permissao, artefato, confirmacao, correlation_id ou causa de falha.

## Evidencias

Registrar evidencias em estrutura versionada e rastreavel.

## Monitoramento

Expor status, ultima execucao, proxima execucao, retries, falhas, correlation_id e evidencia no monitoramento operacional.

## Decisao

Nao considerar concluido sem evidencia operacional.
