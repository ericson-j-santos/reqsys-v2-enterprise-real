# Recuperação operacional do worker Redis

Na inicialização, o worker move atomicamente os jobs remanescentes da fila de processamento para a fila principal antes de consumir novos itens.

## Garantias

- nenhuma perda entre leitura e reentrada, usando `RPOPLPUSH`;
- operação idempotente quando não existem jobs órfãos;
- recuperação executada antes do primeiro consumo;
- quantidade recuperada registrada em log estruturado.

## Limite atual

A recuperação considera todos os itens presentes na fila de processamento como órfãos no momento da inicialização. Topologias com múltiplos workers devem evoluir para lease por job antes de executar recuperação concorrente.
