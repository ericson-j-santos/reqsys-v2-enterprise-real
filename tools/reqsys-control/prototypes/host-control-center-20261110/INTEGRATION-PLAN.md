# Plano de integração governada — sem execução real
## Estado e responsáveis
| Etapa | Fonte / alvo canônico | Estado | Responsável |
|---|---|---|---|
| Interface existente | `tools/reqsys-control` | Código na main, publicação separada | ReqSys Produto |
| API de prontidão (DEV) | `tools/host-readiness-dashboard` | Backend read-only presente; fonte independente pendente | Runtime Platform |
| TODO Global | `backend/app/api/todo_global_adapter.py` | Adaptação read-only descrita, operação real não verificada | Engineering Control Plane |
| Gateway | `reqsys#1705` e Command Gateway canônico | Sem sessão/atestado atual | Runtime Platform |
| Retomada cross-host | `e2e-platform#10` | BLOQUEADO; pickup individual insuficiente | E2E Platform |
| UI estática deste checkpoint | HTML autocontido | Testado localmente, não integrado | ReqSys Produto |

## Etapas fail-closed
1. Revalidar main/HEAD, documentação, issue, orçamento/hard stop e os contratos dos adaptadores. Nada em README, issue, log ou importação autoriza o host.
2. Coletar por API/Gateway autenticados e confiáveis **sem GUI/terminal genérico**: identidade física de cada host, labels/version runner, perfil NORMAL, `SESSION_LAUNCH_OK`, `state_validated=true`, worktree exclusivo, lease/fencing, SHA, dependências, custos e versão das regras. Falta de qualquer gate => `ready_for_work=false`.
3. Autenticar o dashboard e consultar TODO Global pela API backend com RBAC; não transportar token ao browser, não relaxar CORS ou publicar endpoint privado.
4. Para mutações previamente autorizadas, o backend realiza validação de allowlist, ambiente, escopo, consentimento, custo, idempotency key, expected_head_sha e registro durável. Labels/admin exigem confirmação específica. O painel não executa comandos.
5. Handoff: uma única tarefa `request_id` entre dois hosts físicos distintos; checkpoint CAS create-only hash relido; libertação/obtenção exclusiva de lease; Validator independente; replay negativo, sem duplicação; prova de fonte externa.
6. E2E real e leitura independente na mesma versão/SHA, CI/PR gates completos; publicar o evento idempotente para TODO Global somente pela lane autorizada e confirmar readback. Depois de merge autorizado, revalidar a versão resultante.

## Bloqueios atuais
- `HOST_READINESS_UNATTESTED`: falta recibo confiável contemporâneo para os quatro hosts.
- `BLOCKED_PHYSICAL_CROSS_HOST_E2E`: issue `e2e-platform#10` aberta, sem prova mesma tarefa em 2 hosts.
- `TODO_GLOBAL_SYNC_PENDING`: sem recibo de escrita/leitura do evento canônico.
- `READY_FOR_PR_PENDING`: este snapshot não comprova admissibilidade à PR no HEAD atual.
- `COST_UNKNOWN_BLOCKED` para qualquer recurso medido com saldo/hard stop não verificados.

Não criar nova rota paralela ao control plane. Reaproveitar as duas integrações já presentes no ReqSys.
