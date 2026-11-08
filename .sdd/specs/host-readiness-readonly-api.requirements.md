# ReqSys Host Readiness — Requisitos SDD

## Objetivo
Adicionar painel operacional em português e API de evidências autenticada, DEV/loopback, sem dispatch, reboot, merge, Docker ou automação por GUI. Fonte de alinhamento: e2e-platform#10.

## Requisitos
1. Exibir os três hosts autorizados e comparar versão, labels, perfil NORMAL, SHA, SESSION_LAUNCH_OK, Gateway, worktree, lease, dependências nativas, custo e bloqueios.
2. Registrar evidência, data, ação humana e próxima ação; anotações locais nunca viram prova externa.
3. API HTTP Basic autenticada local, GET somente leitura; POST/PUT/PATCH/DELETE rejeitados; credenciais por ambiente, nunca em código ou logs.
4. Persistência SQLite com ingestão separada, event_id idempotente, readback SHA-256, assinatura HMAC e revalidação na leitura.
5. Falhar fechado com assinatura ou identidade adulterada, SHA não admitido, perfil ESTUDO, evidência vencida, custo desconhecido, ausência de Gateway e lease.
6. A seleção de host é para avaliação, não autorização operacional. Pickup individual não prova E2E entre hosts; continuidade permanece bloqueada até dois hosts distintos retomarem a mesma tarefa com checkpoint, replay e validador independente.
7. Sem inventar prova física: coletor oficial GitHub+Gateway precisa ser integrado e homologado por Runtime Platform.

## Controles negativos
Rejeitar ausência de autenticação, método de escrita, assinatura inválida, futuro, expiração, gates falsos, identidade e SHA divergentes, replay conflitante e adulteração do banco.

## Critérios de aceite
- `tools/host-readiness-dashboard/tests/test_readiness.py` aprova casos positivos/negativos e idempotência.
- Sintaxe JavaScript e JSON válida.
- `Pre-PR Readiness Gate` verde no HEAD exato, com `sdd:contract=passed`.
- PR apenas após READY_FOR_PR; E2E físico, CI de PR, revisão independente, merge e deploy permanecem etapas distintas e não concluídas.

## Incremento: observação read-only de pickups GitHub (08/11/2026)

8. A consulta `GET /api/v1/github-observations` requer a autenticação HTTP atual e acessa somente endpoints oficiais GitHub e repositórios permitidos para Desktop, Lenovo e Noteri, sem redirecionamentos, execução no host ou métodos de mutação.
9. Jobs aprovados são apenas **observação auxiliar**: exigem identidade de runner, ID físico e etapa de qualificação realmente concluída; nenhum job ou histórico concede `ready_for_work` ou `continuity_certified`.
10. Ausência de dados, idade maior que 300 segundos, jobs skipped, API indisponível e respostas alteradas falham fechado. Token opcional somente por variável de ambiente protegida; nunca em resposta, log ou artefato.

### Critérios de aceite adicionais

- `tools/host-readiness-dashboard/tests/test_github_observer.py` cobre positivo, identidade divergente, passo ausente, evidência vencida, indisponibilidade, URL proibida, replay e autenticação/método HTTP real, sem acessar GitHub nem host nos testes.
- A consulta não substitui o recibo independente GitHub/Gateway, CAS, lease, validação física, custo zero e gates atuais; o resultado do E2E entre computadores continua bloqueado.
