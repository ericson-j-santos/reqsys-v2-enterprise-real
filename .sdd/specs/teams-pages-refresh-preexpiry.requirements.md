# ReqSys Pages — renovação preventiva governada

## Contexto e causa comprovada

Em 03/11/2026, a issue #3124 foi encerrada após o produtor Teams #41711150474, o publicador Pages #41714019457 e o monitor real #41652009978 (tentativa 2) confirmarem HTTP, contrato e frescor.

O produtor é periódico; a publicação exige exclusivamente `deploy-reqsys-pages-composite.yml` com `workflow_dispatch`, `expected_sha` e autorização explícita `DEPLOY_PAGES`. A atualização dos dados publicados é distinta do SLO de entrega real das mensagens ao Teams.

## Requisitos

1. Reutilizar o monitor existente, sem criar segundo publicador nem introduzir `pages: write`.
2. Avaliar apenas `dashboard-health-evidence/health.json`, obtido da URL pública, com timestamp UTC recente, HTTP 200, esquema reconhecido, `state=healthy` e `errors=[]`.
3. Idade inferior a 24 horas: nenhuma solicitação de publicação.
4. Idade de 24 até 48 horas inclusive: abrir uma única solicitação preventiva de aprovação, sem duplicidade por replay.
5. Evidência inválida, expirada, não saudável, futura ou antiga deve bloquear apenas a política preventiva; o incidente e o gate de indisponibilidade originais do monitor permanecem funcionais, no limite de 48 horas.
6. Somente o proprietário pode solicitar a renovação via `/reqsys run deploy-pages-current-main` na issue #1705; o gateway verifica o SHA atual e encaminha exclusivamente ao publicador canônico, que exige autorização, produtor válido e artefato.
7. Após publicação e leitura independente saudável com dados abaixo de 24 horas, encerrar somente a issue de renovação preventiva. Não encerrar incidentes de SLO ou runtime físico.
8. Preservar custo adicional R$ 0,00, sem segredos, alteração de permissões nem publicação automática.

## Critérios de aceite

- [ ] Positivo: 23,99 horas retorna `fresh`, sem deploy.
- [ ] Limiares: 24 e 48 horas retornam `renewal_required`, sem deploy.
- [ ] Negativos: idade superior a 48 horas, HTTP 503, erro de contrato, idade NaN, booleano, timestamp desatualizado ou futuro e monitor `unhealthy` bloqueiam a política preventiva.
- [ ] Idempotência: replay não cria segunda issue; avaliação com mesmos dados e instante produz resultado equivalente.
- [ ] O avaliador não contém `actions/deploy-pages@` nem `pages: write`; a publicação permanece exclusiva do gateway e do publicador canônico.
- [ ] O monitor continua abrindo e fechando incidentes de disponibilidade somente por evidência HTTP real.
- [ ] `READY_FOR_PR`, testes e CI são aprovados no HEAD exato antes da PR e do merge.
- [ ] E2E pós-integração verifica o monitor recorrente com observação pública e, quando aplicável, solicitação idempotente de renovação. Sem esse E2E, estado `PARCIAL`.
- [ ] Custo adicional máximo R$ 0,00.

## Mapeamento de testes

- `tests/test_teams_pages_refresh_policy.py`
- `tests/test_live_dashboard_post_merge_trigger.py`
- `tests/test_pages_single_writer_guard.py`

## Operação e autorização

Engenharia ReqSys responde por código, testes e rastreabilidade. O proprietário `ericson-j-santos` autoriza publicações no gateway da issue #1705. A política não executa deploy. TODO Global permanece pendente de recibo canônico.
