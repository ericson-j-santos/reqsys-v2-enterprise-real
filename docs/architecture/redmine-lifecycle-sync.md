# Reconciliação de lifecycle ReqSys ↔ Redmine

Issue de referência: #1686. Documento cobre o reconciliador por requisito
(incremento 1) e a execução em lote governada (incremento 2).

Não confundir com `docs/architecture/redmine-sync-queue.md`: aquela fila trata
da **criação** inicial de issue a partir do fluxo Planner → Dataverse → Redmine.
Aqui o assunto é a **reconciliação contínua** de um requisito que já possui
issue vinculada.

## Propriedade de campos

| Campo | Fonte canônica | Direção permitida |
|---|---|---|
| código/identidade do requisito | ReqSys | não sincroniza |
| título (`subject`) | ReqSys | ReqSys → Redmine |
| descrição (`description`) | ReqSys | ReqSys → Redmine |
| status de execução | Redmine | Redmine → ReqSys (snapshot) |
| responsável | Redmine | Redmine → ReqSys (snapshot) |
| percentual concluído | Redmine | Redmine → ReqSys (snapshot) |
| journals/comentários | Redmine | Redmine → ReqSys (auditoria) |

Campo sem proprietário explícito não é sincronizado. O snapshot vindo do Redmine
não altera automaticamente o status funcional governado do requisito.

## Componentes

| Componente | Responsabilidade |
|---|---|
| `backend/app/services/redmine_lifecycle_sync.py` | reconciliação de um requisito: diff por fingerprint, `PUT` idempotente, releitura independente obrigatória, checkpoint de journals |
| `backend/app/services/redmine_lifecycle_batch.py` | lote governado: reserva por requisito, backoff, quarentena, agregados |
| `POST /requisitos/lifecycle/{id}/sincronizar-redmine` | reconciliação individual (`lifecycle:write`) |
| `POST /requisitos/lifecycle/sincronizar-redmine/lote` | reconciliação em lote (`lifecycle:write`) |
| `POST /requisitos/lifecycle/{id}/sincronizar-redmine/liberar-quarentena` | saída explícita de quarentena (`lifecycle:write`) |

## Estado persistido

Duas linhas distintas de `VinculoGit`, ambas com `provedor='redmine'` e
`referencia=<issue_id>`:

- `tipo='redmine_sync_state'` — checkpoint do incremento 1: fingerprints e
  `last_journal_id`;
- `tipo='redmine_sync_control'` — controle do incremento 2: `lock`, `attempts`,
  `next_attempt_at`, `quarantined`, `quarantine_reason`, `last_success_at`.

A separação é deliberada: o incremento 1 reescreve seu estado por completo, e
misturar os dois faria uma escrita apagar a outra. Nenhuma migração de schema é
exigida neste incremento.

## Reserva (lock) por requisito

O lock vive dentro do JSON de controle e é adquirido por **compare-and-swap** no
próprio `UPDATE`:

```sql
UPDATE vinculos_git SET titulo = :novo
 WHERE id = :id AND titulo = :valor_lido
```

`rowcount = 0` significa que outra sessão avançou o estado; o requisito é
retornado como `pulado_lock` em vez de processado em paralelo. O lock expira em
`REDMINE_LIFECYCLE_SYNC_LOCK_TIMEOUT_MINUTOS`, então um worker morto não trava a
fila permanentemente.

Sem constraint única disponível neste incremento, a criação concorrente da linha
de controle é tolerada: a canônica é sempre o menor `id` e a duplicata criada
pela própria sessão é removida em seguida.

## Backoff e quarentena (DLQ)

- cada falha incrementa `attempts`, registra `last_error` e agenda
  `next_attempt_at = agora + min(base * 2^(attempts-1), teto)`;
- ao atingir `REDMINE_LIFECYCLE_SYNC_MAX_TENTATIVAS`, o requisito entra em
  quarentena: sai do lote e não é mais retentado automaticamente;
- a saída da quarentena é explícita e auditada — conflito permanente é decisão
  operacional, não retentativa infinita.

Eventos de auditoria: `REDMINE_SYNC_FALHA`, `REDMINE_SYNC_QUARENTENA`,
`REDMINE_SYNC_QUARENTENA_LIBERADA`, além de
`REDMINE_SYNC_REQSYS_TO_REDMINE`, `REDMINE_SYNC_REDMINE_TO_REQSYS` e
`REDMINE_JOURNAL_IMPORTADO` do incremento 1. Todos carregam `correlation_id`.

## Configuração

| Variável | Padrão | Efeito |
|---|---|---|
| `REDMINE_LIFECYCLE_SYNC_LOTE_MAX` | `10` | teto de requisitos por lote |
| `REDMINE_LIFECYCLE_SYNC_LOCK_TIMEOUT_MINUTOS` | `10` | validade da reserva |
| `REDMINE_LIFECYCLE_SYNC_MAX_TENTATIVAS` | `5` | falhas até quarentena |
| `REDMINE_LIFECYCLE_SYNC_BACKOFF_BASE_MINUTOS` | `5` | base do backoff exponencial |
| `REDMINE_LIFECYCLE_SYNC_BACKOFF_MAX_MINUTOS` | `240` | teto do backoff |

API key do Redmine vem da configuração de segredos existente; nada de
credencial no repositório.

## Controles contra loop e falso positivo

- `dry_run` tem formato de resposta distinto do processamento real, não adquire
  lock e não cria estado de controle;
- `HTTP 2xx` do Redmine não é aceito como prova: após o `PUT` a issue é relida e
  a reconciliação falha se o efeito não for confirmado;
- fingerprint impede reenvio sem mudança — repetir a mesma entrada produz zero
  mutações adicionais;
- journal já processado não é reimportado (checkpoint pelo maior `journal_id`);
- requisito sem vínculo Redmine válido falha fechado, sem sincronizar.

## Estado de validação

- unitários e de contrato de API: verdes (`backend/tests/test_redmine_lifecycle_sync*.py`,
  `backend/tests/test_redmine_lifecycle_batch*.py`), incluindo caso positivo,
  negativo, idempotência, concorrência de lock e ciclo de quarentena;
- teste do próprio teste executado: defeitos injetados (ignorar lock ativo e
  nunca quarentenar) reprovaram exatamente os testes correspondentes, e a
  injeção foi revertida antes da validação final;
- **E2E real contra instância Redmine configurada: pendente.** Enquanto não
  houver esse ciclo, o incremento permanece `parcialmente validado`.

## Próximo incremento

- agendamento governado em DEV chamando o endpoint de lote com service token e
  intervalo configurável;
- fallback de polling e webhook somente onde suportado e configurado com
  segurança;
- E2E real: alterar título/descrição no ReqSys, confirmar no Redmine por leitura
  independente, alterar status/responsável/progresso e comentário no Redmine,
  reconciliar de volta, repetir sem mudanças exigindo zero mutações e simular
  falha de API confirmando backoff/quarentena sem duplicidade.
