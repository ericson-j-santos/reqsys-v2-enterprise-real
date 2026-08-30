# Adaptador Pentaho → ReqSys

## Objetivo

Padronizar a entrada de lotes do Pentaho no ReqSys sem mover regras críticas de negócio para arquivos `.ktr`/`.kjb`.

O Pentaho atua como produtor: extrai, normaliza e envia. O ReqSys persiste o lote, garante idempotência, processa de forma assíncrona, registra evidência e direciona falhas para quarentena.

## Contrato v1

`POST /api/integracoes/pentaho/lotes`

Cabeçalhos obrigatórios:

- `Authorization: Bearer <JWT admin>` ou `X-Service-Token: <token>` com escopo `pentaho:integracao`;
- `X-Correlation-Id`: identificador de rastreabilidade do fluxo;
- `Idempotency-Key`: chave estável do lote, com até 128 caracteres.

Exemplo:

```json
{
  "origem": "PENTAHO",
  "processo": "PRODUTOS_DIARIOS",
  "versaoEntrada": 1,
  "dataReferencia": "2026-08-29",
  "lote": "20260829-001",
  "registros": [
    {
      "produto": 10001,
      "canal": "WEB",
      "servico": "ANALISE"
    }
  ]
}
```

Resposta: `202 Accepted`.

```json
{
  "loteId": "0c9e6d1d-...",
  "correlationId": "7f15...",
  "status": "PENDENTE",
  "duplicado": false,
  "consulta": "/api/integracoes/pentaho/lotes/0c9e6d1d-..."
}
```

A versão inicial aceita `versaoEntrada = 1`. O limite padrão é 10.000 registros por lote e pode ser ajustado por `REQSYS_PENTAHO_MAX_REGISTROS`.

## Idempotência

A coluna `idempotency_key` possui restrição única no banco. Reenvios com a mesma chave e o mesmo conteúdo retornam o mesmo `loteId` com `duplicado=true`, inclusive sob concorrência. Se a mesma chave for reutilizada com conteúdo diferente, o ReqSys rejeita a solicitação com HTTP `409 Conflict`, evitando associar duas cargas distintas ao mesmo lote.

Uma chave recomendada é o SHA-256 de:

`processo + dataReferencia + lote + hash-do-arquivo-normalizado`

O token de serviço e qualquer segredo devem ser fornecidos por variável/gerenciador de credenciais do ambiente; nunca devem ser gravados no `.ktr`, `.kjb` ou repositório.

## Fila, consumidor e estados

A tabela `pentaho_integration_batches` é a fila durável do adaptador.

Fluxo normal:

`PENDENTE → PROCESSANDO → CONCLUIDO`

Fluxo de falha:

`PENDENTE → PROCESSANDO → QUARENTENA`

A passagem `PENDENTE → PROCESSANDO` é feita por atualização atômica condicionada ao estado. Assim, o processamento imediato disparado pela API e o consumidor independente podem encontrar o mesmo lote sem executá-lo duas vezes: apenas um processo consegue reivindicá-lo.

O consumidor independente é executado por:

```bash
python -m app.workers.pentaho_integration_worker
```

Para diagnóstico ou execução única:

```bash
python -m app.workers.pentaho_integration_worker --once
```

No Fly.io atual, API e consumidor são processos separados dentro da mesma máquina. Essa escolha é intencional porque a produção ainda utiliza SQLite em volume persistente; criar grupos de processo em máquinas Fly distintas separaria o acesso ao volume. Quando o banco for migrado para PostgreSQL ou SQL Server compartilhado, o consumidor poderá ser movido para uma máquina própria sem alterar o contrato da fila.

`CONCLUIDO` neste adaptador significa que o transporte, persistência e validação estrutural foram concluídos. Regras de domínio continuam pertencendo aos consumidores do ReqSys.

## Recuperação após interrupção

O consumidor verifica lotes em `PROCESSANDO` cuja última atualização ultrapassou a janela configurada. Esses lotes são considerados abandonados, como em reinicialização da máquina ou término inesperado do processo.

Comportamento:

1. lote interrompido abaixo do limite de tentativas volta para `PENDENTE`;
2. a próxima reivindicação incrementa `tentativas` e volta a processá-lo;
3. lote interrompido repetidamente até o limite vai para `QUARENTENA`;
4. o `correlationId` e a chave de idempotência permanecem inalterados;
5. a recuperação é registrada em log sem conteúdo sensível do payload.

Configurações:

| Variável | Padrão | Finalidade |
| --- | ---: | --- |
| `REQSYS_PENTAHO_WORKER_ENABLED` | `true` | habilita o consumidor supervisionado no runtime Fly |
| `REQSYS_PENTAHO_WORKER_POLL_SECONDS` | `1` | intervalo entre buscas por lotes pendentes |
| `REQSYS_PENTAHO_WORKER_WATCHDOG_SECONDS` | `2` | intervalo de supervisão e reinício do processo consumidor |
| `REQSYS_PENTAHO_PROCESSING_TIMEOUT_SECONDS` | `300` | tempo para considerar `PROCESSANDO` abandonado |
| `REQSYS_PENTAHO_MAX_TENTATIVAS` | `5` | limite antes de enviar interrupções repetidas para quarentena |
| `REQSYS_PENTAHO_MAX_REGISTROS` | `10000` | limite estrutural de registros por lote |

O `scripts/fly_boot.sh` supervisiona o consumidor. Se ele encerrar enquanto a API continuar ativa, o processo é iniciado novamente. Se a máquina inteira reiniciar, a fila permanece no volume e o consumidor recupera os lotes abandonados na próxima inicialização.

## Consulta do lote

`GET /api/integracoes/pentaho/lotes/{loteId}`

Retorna situação, contadores, tentativas, erro sanitizado e datas da execução.

## Reprocessamento

`POST /api/integracoes/pentaho/lotes/{loteId}/reprocessar`

Somente lotes em `QUARENTENA` podem ser reenfileirados. A chave de idempotência e o `correlationId` originais são preservados.

## Painel operacional

Frontend: `/integracoes/pentaho`

API: `GET /api/integracoes/pentaho/dashboard`

O painel apresenta:

- lotes recebidos no dia;
- concluídos;
- pendentes/processando;
- quarentena;
- última execução por processo;
- lotes recentes;
- reprocessamento de lotes em quarentena.

## Configuração no Pentaho 7.1

Fluxo recomendado no job/transformação:

1. ler e normalizar a origem;
2. gerar o JSON no contrato v1;
3. obter `X-Correlation-Id` e `Idempotency-Key` sem segredo embutido;
4. executar `POST /api/integracoes/pentaho/lotes`;
5. aceitar `202` como entrega confirmada ao adaptador;
6. persistir o `loteId` retornado;
7. consultar `GET /api/integracoes/pentaho/lotes/{loteId}` quando o processo precisar aguardar o resultado;
8. não reenviar com nova chave após timeout sem antes consultar o lote original.

## Controles de segurança e resiliência

- autenticação de serviço escopada por `pentaho:integracao`;
- deduplicação no banco, não apenas em memória;
- reutilização divergente de chave de idempotência bloqueada com `409`;
- reivindicação atômica para impedir consumo concorrente duplicado;
- recuperação de processamento interrompido;
- limite de tentativas com quarentena;
- consumidor supervisionado e reiniciado automaticamente;
- payload não incluído em mensagens de log de erro;
- correlação ponta a ponta;
- limite configurável de registros;
- reprocessamento restrito;
- erros persistidos sem incluir credenciais.

## Critério de conclusão

O incremento está concluído quando os testes de contrato, idempotência, reivindicação atômica, recuperação de lote abandonado, limite de tentativas, quarentena, reprocessamento e painel estiverem verdes no CI e a branch estiver sem conflito com `main`.
