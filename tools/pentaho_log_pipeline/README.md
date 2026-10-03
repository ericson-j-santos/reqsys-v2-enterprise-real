# Pipeline governado de logs Pentaho

## Objetivo

Preservar o agendamento atual por `cron` e a execução via Pentaho/Kitchen, mas
retirar do filesystem a responsabilidade de representar o estado do processo.
O SQL Server passa a controlar ingresso, idempotência, reserva concorrente,
retentativa, quarentena, DLQ, arquivamento e expurgo.

O conteúdo do log não é persistido no banco. O banco guarda somente metadados,
caminho, tamanho, SHA-256, estados e correlação.

## Fluxo

```text
cron
  -> run_pentaho_with_queue.sh
      -> kitchen.sh
          -> log bruto em PENTAHO_LOG_DIR
      -> pipeline.py enqueue
          -> SQL Server / OPENJSON
              -> AGUARDANDO
                  -> worker
                      -> PROCESSANDO (lease)
                          -> CONCLUIDO -> archive/YYYY/MM/DD
                          -> FALHA -> retry
                          -> DLQ após 3 tentativas
                  -> purge após retenção
                      -> EXPURGADO
                      -> EXPURGO_DLQ após 3 tentativas

entrada estrutural inválida -> pentaho_log_quarentena
```

## Pré-requisitos

- Linux com Python 3.10+;
- Pentaho Data Integration com `kitchen.sh`;
- SQL Server 2017+;
- Microsoft ODBC Driver para SQL Server no host Linux;
- `pyodbc` instalado a partir de `requirements.txt`;
- credencial SQL Server fornecida por variável de ambiente/cofre, nunca no
  script ou no repositório.

## 1. Instalar o contrato SQL

Execute, na base destinada ao controle operacional:

```bash
sqlcmd -S "$SQLSERVER_HOST" -d "$SQLSERVER_DB" \
  -i tools/pentaho_log_pipeline/sql/001_pentaho_log_pipeline.sql
```

O script é idempotente para criação das tabelas e recria os procedimentos com
`CREATE OR ALTER`.

Objetos principais:

- `dbo.pentaho_log_execucao` — execução real do Pentaho;
- `dbo.pentaho_log_fila` — fila durável e estados;
- `dbo.pentaho_log_quarentena` — metadados estruturalmente inválidos ou
  conflito de idempotência;
- `dbo.sp_pentaho_log_ingestir_json` — ingresso em lote via `OPENJSON`;
- `dbo.sp_pentaho_log_reservar` — reserva com `UPDLOCK`, `READPAST` e
  `ROWLOCK`;
- procedimentos de conclusão, falha e expurgo.

## 2. Configurar o host Linux

Exemplo de variáveis. Os valores reais devem vir do mecanismo de segredos do
ambiente:

```bash
export PENTAHO_LOG_SQLSERVER_CONNECTION='Driver={ODBC Driver 18 for SQL Server};Server=...;Database=...;UID=...;PWD=...;Encrypt=yes;TrustServerCertificate=no'
export PENTAHO_LOG_ROOT='/var/log/pentaho/raw'
export PENTAHO_LOG_ARCHIVE_ROOT='/var/log/pentaho/archive'
export PENTAHO_LOG_DIR='/var/log/pentaho/raw'
export KETTLE_HOME='/opt/pentaho/data-integration'
export PENTAHO_JOB='/opt/pentaho/jobs/carga_clientes.kjb'
export PENTAHO_PROCESS_NAME='CARGA_CLIENTES'
```

Instalação Python:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r tools/pentaho_log_pipeline/requirements.txt
```

## 3. Executar sem alterar o cron ainda

Primeiro faça uma execução controlada fora do agendamento:

```bash
bash tools/pentaho_log_pipeline/run_pentaho_with_queue.sh
```

O wrapper:

1. gera `execution_id` e `correlation_id`;
2. executa o `kitchen.sh` sem mudar o job Pentaho;
3. grava stdout/stderr no log bruto;
4. calcula SHA-256 e envia somente metadados ao SQL Server;
5. preserva o código de saída do Pentaho;
6. quando o Pentaho termina com sucesso mas a publicação na fila falha,
   retorna `70` para impedir falso positivo no cron.

## 4. Consumidor de arquivamento

Execução única para diagnóstico:

```bash
python tools/pentaho_log_pipeline/pipeline.py worker --once
```

Execução contínua:

```bash
python tools/pentaho_log_pipeline/pipeline.py worker \
  --batch-size 3 \
  --lease-seconds 300 \
  --retry-seconds 120 \
  --retention-days 30
```

A reserva é atômica. Um consumidor ignora itens reservados por outro. Um item
em `PROCESSANDO` cujo lease expirou volta a ser elegível. Cada nova reserva
incrementa `tentativas`; depois da terceira falha o item vai para `DLQ` e não é
mais reservado automaticamente.

O arquivamento usa destino determinístico:

```text
<PENTAHO_LOG_ARCHIVE_ROOT>/YYYY/MM/DD/<execucao_id>_<arquivo-original>
```

Antes de remover a origem, o worker copia, sincroniza, recalcula SHA-256 e
valida o destino. Se ocorrer crash entre a criação do destino e a consolidação
no SQL Server, a reexecução reconhece o mesmo SHA-256 e conclui sem duplicar.

## 5. Consumidor de expurgo

```bash
python tools/pentaho_log_pipeline/pipeline.py purge --once
```

ou continuamente:

```bash
python tools/pentaho_log_pipeline/pipeline.py purge --batch-size 3
```

Somente itens `CONCLUIDO` cuja `retencao_ate` venceu são elegíveis. O SHA-256 é
validado antes da exclusão. Arquivo já ausente é tratado como repetição
idempotente e o estado pode ser consolidado em `EXPURGADO`.

## 6. Troca segura do cron

Não remova a entrada atual antes da execução controlada e da validação E2E. A
mudança mínima é substituir apenas o comando executado pelo cron:

```cron
# antes
0 * * * * /caminho/script-atual.sh

# alvo, somente depois da validação
0 * * * * /caminho/reqsys/tools/pentaho_log_pipeline/run_pentaho_with_queue.sh
```

O worker e o expurgo podem ser executados por `systemd`, supervisor ou entradas
separadas de cron. O primeiro incremento não exige trocar o agendador.

## Idempotência

O produtor calcula:

```text
SHA256(processo + "|" + execution_key + "|" + SHA256(log))
```

O SQL Server mantém `UNIQUE(idempotency_key)` e `UNIQUE(execucao_id)`. Reenvio
do mesmo lote não cria nova execução nem nova fila. Reutilização divergente de
`execution_id` ou `idempotency_key` é direcionada para quarentena.

## Estados

| Estado | Significado |
| --- | --- |
| `AGUARDANDO` | disponível para consumidor |
| `PROCESSANDO` | reservado por lease |
| `FALHA` | falha transitória, abaixo do limite |
| `DLQ` | três tentativas de arquivamento atingidas |
| `CONCLUIDO` | arquivo validado e arquivado |
| `EXPURGANDO` | expurgo reservado |
| `EXPURGO_FALHA` | falha transitória de expurgo |
| `EXPURGO_DLQ` | três tentativas de expurgo atingidas |
| `EXPURGADO` | arquivo removido após retenção |

Quarentena não é estado da fila: ela recebe entradas estruturalmente inválidas
antes da criação do item.

## Validação

### Testes Python sem SQL Server

```bash
pytest -q tests/test_pentaho_log_pipeline.py
```

Cobrem:

- chave idempotente estável;
- partição `YYYY/MM/DD`;
- SHA-256 antes/depois do arquivamento;
- recuperação idempotente após crash;
- bloqueio de caminho fora da raiz permitida;
- bloqueio de arquivo alterado depois do ingresso;
- expurgo com validação de hash e repetição idempotente.

### Contrato SQL Server

Depois de instalar `001_pentaho_log_pipeline.sql`, execute:

```bash
sqlcmd -S "$SQLSERVER_HOST" -d "$SQLSERVER_DB" \
  -i tools/pentaho_log_pipeline/sql/900_contract_test.sql
```

O teste roda dentro de transação e executa `ROLLBACK` ao final. Ele exige:

- primeira carga: 4 entradas e 1 quarentena;
- repetição do mesmo lote: 0 entradas e 0 novas quarentenas;
- exatamente três reservas;
- tentativa `1` nas três reservas;
- persistência independente dos três estados `PROCESSANDO`.

Saída esperada:

```text
contract_test  carga1_inseridos  carga1_quarentenados  carga2_inseridos  carga2_quarentenados  reservados
PASS           4                 1                     0                 0                     3
```

## E2E de aceite no Linux

Use um job Pentaho não produtivo e um marcador único. O incremento só deve ser
considerado concluído quando houver evidência da mesma execução para:

1. `run_pentaho_with_queue.sh` gera um log real e uma linha em
   `pentaho_log_execucao`;
2. repetir o mesmo `execution_id`/`execution_key` não duplica fila;
3. `worker --once` move o arquivo para a partição esperada;
4. leitura independente confirma `CONCLUIDO`, SHA-256 e destino;
5. um arquivo deliberadamente alterado depois do ingresso é rejeitado e não é
   removido;
6. uma reserva abandonada é recuperada após o lease;
7. três falhas levam a `DLQ` e a quarta reserva não ocorre;
8. após retenção controlada, `purge --once` remove o arquivo e a ausência é
   confirmada no filesystem antes de `EXPURGADO`.

## Rollback

Enquanto o cron não tiver sido trocado, rollback funcional é simplesmente não
usar o wrapper/worker. Os objetos SQL podem permanecer sem impacto no Pentaho.
Não remova tabelas com histórico sem aprovação explícita de operação destrutiva.
