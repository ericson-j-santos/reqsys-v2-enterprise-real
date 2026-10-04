# Email Operations Center v1

## Objetivo

Recuperar e integrar à arquitetura atual da `main` o núcleo governado de operações de e-mail, preservando rastreabilidade por `correlation_id`, fila, retry, dead-letter queue, replay, timeline e métricas sem acoplar provider real nem credenciais.

## Requisitos

1. O núcleo deve validar assunto, destinatários, `correlation_id` e número mínimo de tentativas.
2. O processamento deve registrar estados `QUEUED`, `PROCESSING`, `SENT`, `RETRY_SCHEDULED`, `DEAD_LETTER` e `REPLAYED`.
3. Falhas temporárias devem agendar nova tentativa até `max_attempts`; o esgotamento deve mover a operação para DLQ.
4. Replay deve ser permitido apenas para operações em DLQ.
5. Timeline e métricas devem refletir o estado efetivo sem exigir credenciais externas.
6. O provider fake deve manter testes determinísticos e nenhum segredo deve ser necessário para CI.
7. A recuperação deve permanecer no mesmo PR e reconciliada com a `main` corrente, sem force-push.

## Critérios de aceite

- `backend/tests/test_email_operations_center.py` verde no HEAD atual.
- Pre-PR Readiness com `sdd:contract=passed` no HEAD atual.
- Branch com `behind_by=0` em relação à `main` corrente antes de merge.
- Nenhum gate obrigatório vermelho no HEAD usado para decisão de merge.
