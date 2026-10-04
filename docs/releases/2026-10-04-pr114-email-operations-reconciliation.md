# Reconciliação do PR #114 — Email Operations Center

## Estado observado

O PR #114 propôs uma primeira versão em memória para fila, retry, DLQ, replay, timeline e métricas de envio de e-mail.

A `main` atual já evoluiu essa necessidade para a arquitetura de `movimento_email`, com capacidades mais fortes:

- fila persistente em banco;
- reserva concorrente e recuperação de reservas travadas;
- `retry_count` e limite configurável de tentativas;
- consumer separado;
- envio SMTP/Graph com resiliência;
- auditoria por `correlation_id`;
- endpoints de execução, consumo e status;
- dashboard operacional autocontido;
- testes de fila, consumer, retries e falhas.

## Decisão

Não restaurar `email_operations_center.py` em memória como uma segunda fila paralela. Isso criaria dois modelos operacionais concorrentes e perderia as garantias de persistência e recuperação já presentes na implementação atual.

## Preservação do trabalho

Os conceitos do #114 foram absorvidos pela camada de e-mail atual: fila governada, retry, observabilidade e estado operacional permanecem ativos, agora de forma persistente.

## Critério de conclusão

- branch sincronizada com a `main`;
- nenhum centro de fila paralelo reintroduzido;
- `behind_by=0`;
- PR sem conflitos;
- gates obrigatórios verdes no HEAD reconciliado.
