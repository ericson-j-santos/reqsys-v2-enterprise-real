# Central Global — plano de controle operacional

Núcleo determinístico da Central de Solicitações de IA. Resolve três gargalos
transversais: roteamento de executor, limite de trabalho simultâneo e prova de
conclusão.

## Ciclo canônico

```
solicitação → causa raiz → executor → execução → validação → evidência
```

A Solicitação de Trabalho (`WorkRequest`) é a unidade única de estado. O
executor nunca é escolhido pelo produtor: a Central classifica.

## Componentes

| Componente | Módulo | Responsabilidade |
| --- | --- | --- |
| Executor Router | `runtime/app/domain/central/executor_router.py` | Classifica a solicitação em um executor por regra nomeada e auditável |
| WIP por causa raiz | `runtime/app/domain/central/wip_policy.py` | Limita causas raiz ativas (default 3), não solicitações |
| Evidence Ledger | `runtime/app/domain/central/evidence_ledger.py` | Registro canônico de "comprovadamente concluído", vinculado ao SHA |
| Serviço | `runtime/app/application/services/central_service.py` | Fecha o ciclo e impõe as transições válidas |
| API | `runtime/app/api/central.py` | Endpoints sob `/api/central` |

## Regras que o código impõe

1. **Bloqueio de identidade vence roteamento técnico.** Falta de consentimento,
   credencial ou permissão roteia para `human_gate` mesmo que a solicitação
   pareça de CI ou Graph — executar apenas antecipa a falha de autenticação
   para dentro do E2E.
2. **Solicitação sem regra correspondente vai para `human_gate`**, nunca para um
   executor por aproximação.
3. **WIP é contado por causa raiz.** Vinte sintomas de três defeitos ocupam três
   vagas, não vinte. Causa já em andamento mantém a vaga; `wip_breach` sinaliza
   violação em vez de abandonar trabalho iniciado.
4. **`EVIDENCED` exige as quatro verificações em PASS**: caso positivo, controle
   negativo, idempotência e leitura por fonte independente.
5. **Qualquer verificação em FAIL leva a `BLOCKED`.** Parcialidade não é
   arredondada para sucesso.
6. **Evidência é vinculada ao SHA.** Registrar evidência em um SHA novo
   invalida (`SUPERSEDED`) o registro anterior, e a conclusão é recusada com
   HTTP 409 se a evidência corrente não for do SHA da solicitação.

## Endpoints

| Método | Rota | Uso |
| --- | --- | --- |
| POST | `/api/central/work-requests` | Registra e classifica (idempotente por correlation_id + projeto + título) |
| GET | `/api/central/work-requests[/{id}]` | Estado corrente |
| POST | `/api/central/work-requests/{id}/transition` | Transição de ciclo; `409` em transição inválida ou conclusão sem evidência |
| GET | `/api/central/admission-plan` | Plano de WIP: causas admitidas e enfileiradas |
| GET | `/api/central/next[?executor=]` | Próximo item executável; `204` quando não há |
| POST | `/api/central/evidence` | Registra verificações no ledger |
| GET | `/api/central/evidence/{id}` | Leitura independente do ledger |

## Validação E2E

```bash
cd runtime
QUEUE_BACKEND=memory STORAGE_BACKEND=memory \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 &
python scripts/e2e_central.py     # exige instância limpa; código 1 em falha
```

O script cobre caso positivo, três controles negativos (conclusão sem evidência
completa, conclusão após mudança de SHA, `human_gate` fora da fila executável),
idempotência de registro e leitura por endpoint independente.

## Estado e limites conhecidos

* O armazenamento é em memória por processo. Persistência durável (Redis, à
  semelhança de `parallelism_control`) é o próximo incremento.
* Os executores ainda não executam: a Central decide e enfileira o trabalho. O
  acoplamento de cada executor real é incremento subsequente.
* O preflight de identidade (verificação ativa de consentimento, segredo e
  validade antes da fila) não está implementado; hoje o bloqueio é declarado
  pela regra `identity.blocked` a partir dos sinais da solicitação.
