import test from 'node:test'
import assert from 'node:assert/strict'

import {
  adaptiveCardFromMessage,
  evaluateContract,
  evaluatePlannerCard,
  filterMessagesSince,
  messageContainsTitle,
  resolveGraphAuth,
  selectPlannerCandidate,
  validatePollTimeout,
} from '../planner_teams_runtime_e2e.mjs'

test('aprova somente com controle normal presente e E2E ausente', () => {
  assert.deepEqual(
    evaluateContract({ normalFound: true, e2eFound: false, cardPassed: true }),
    { passed: true, reason: 'contract_satisfied' },
  )
})

test('reprova quando a tarefa E2E aparece no Teams', () => {
  assert.deepEqual(
    evaluateContract({ normalFound: true, e2eFound: true, cardPassed: true }),
    { passed: false, reason: 'ct01_e2e_message_observed' },
  )
})

test('reprova quando o controle normal nao aparece', () => {
  assert.deepEqual(
    evaluateContract({ normalFound: false, e2eFound: false, cardPassed: false }),
    { passed: false, reason: 'ct02_normal_message_not_observed' },
  )
})

test('encontra titulo em corpo ou attachment serializado', () => {
  const title = 'REQSYS-AUTOMATED-CONTROL-NORMAL-123'
  assert.equal(messageContainsTitle({ body: { content: `Tarefa: ${title}` } }, title), true)
  assert.equal(messageContainsTitle({ attachments: [{ content: JSON.stringify({ title }) }] }, title), true)
  assert.equal(messageContainsTitle({ body: { content: 'outra tarefa' } }, title), false)
})

function correctedCard(taskId = 'task-123') {
  return {
    type: 'AdaptiveCard',
    version: '1.2',
    body: [
      { type: 'TextBlock', text: 'Nova tarefa no Planner' },
      { type: 'TextBlock', text: 'REQSYS-AUTOMATED-CONTROL-NORMAL-123' },
      {
        type: 'FactSet',
        facts: [
          { title: 'Progresso', value: '0%' },
          { title: 'Vencimento', value: 'Sem prazo' },
        ],
      },
    ],
    actions: [
      {
        type: 'Action.OpenUrl',
        title: 'Abrir no Planner',
        url: `https://planner.cloud.microsoft/webui/plan/plan-dev/view/board/task/${taskId}`,
      },
    ],
  }
}

test('extrai Adaptive Card serializado do attachment Graph', () => {
  const card = correctedCard()
  const message = {
    attachments: [
      {
        contentType: 'application/vnd.microsoft.card.adaptive',
        content: JSON.stringify(card),
      },
    ],
  }
  assert.deepEqual(adaptiveCardFromMessage(message), card)
})

test('aprova contrato visual corrigido do cartão Planner', () => {
  const taskId = 'task-123'
  const result = evaluatePlannerCard(
    { attachments: [{ content: JSON.stringify(correctedCard(taskId)) }] },
    taskId,
  )
  assert.equal(result.passed, true)
  assert.equal(result.reason, 'card_contract_satisfied')
  assert.deepEqual(result.summary.fact_titles, ['Progresso', 'Vencimento'])
  assert.equal(result.summary.has_legacy_plan_fact, false)
  assert.equal(result.summary.has_open_planner, true)
  assert.equal(result.summary.task_link_matches, true)
})

test('reprova cartão legado com Plano e Percentual', () => {
  const taskId = 'task-123'
  const legacy = correctedCard(taskId)
  legacy.body[0].text = 'Nova tarefa criada no Planner'
  legacy.body[2].facts = [
    { title: 'Plano', value: 'VOd3MnuHGEO9lo-bno5BhWUABsm9' },
    { title: 'Percentual', value: '0%' },
    { title: 'Vencimento', value: 'sem prazo' },
  ]
  legacy.actions = []
  const result = evaluatePlannerCard(
    { attachments: [{ content: JSON.stringify(legacy) }] },
    taskId,
  )
  assert.equal(result.passed, false)
  assert.equal(result.reason, 'ct03_card_contract_mismatch')
  assert.equal(result.summary.has_legacy_plan_fact, true)
  assert.equal(result.summary.has_legacy_percentual_fact, true)
  assert.equal(result.summary.has_open_planner, false)
})

test('reprova contrato geral quando mensagem existe mas cartão continua legado', () => {
  assert.deepEqual(
    evaluateContract({ normalFound: true, e2eFound: false, cardPassed: false }),
    { passed: false, reason: 'ct03_card_contract_not_satisfied' },
  )
})

test('descarta mensagens antigas fora da janela de evidência', () => {
  const startedAt = '2026-09-10T12:00:00.000Z'
  const messages = [
    { id: 'antiga', createdDateTime: '2026-09-10T11:58:00.000Z' },
    { id: 'margem', createdDateTime: '2026-09-10T11:59:30.000Z' },
    { id: 'nova', createdDateTime: '2026-09-10T12:01:00.000Z' },
  ]
  assert.deepEqual(filterMessagesSince(messages, startedAt).map((item) => item.id), ['margem', 'nova'])
})

test('aceita somente token Graph obtido por OIDC', () => {
  assert.deepEqual(resolveGraphAuth({ accessToken: 'oidc-token' }), { mode: 'oidc', token: 'oidc-token' })
})

test('ignora client secret legado e falha fechado sem token OIDC', () => {
  assert.throws(
    () => resolveGraphAuth({ accessToken: '', clientSecret: 'legacy-secret' }),
    /graph_auth_ausente:oidc_token_obrigatorio/,
  )
})

test('seleciona o único alvo Planner classificado como DEV', () => {
  const selected = selectPlannerCandidate([
    {
      group_name: 'ReqSys',
      plan_name: 'WSJF Produção',
      plan_id: 'plan-prod',
      bucket_id: 'bucket-prod',
    },
    {
      group_name: 'ReqSys WSJF DEV',
      plan_name: 'WSJF DEV',
      plan_id: 'plan-dev',
      bucket_id: 'bucket-dev',
    },
  ])
  assert.equal(selected.plan_id, 'plan-dev')
  assert.equal(selected.bucket_id, 'bucket-dev')
})

test('reprova descoberta quando existem dois alvos DEV possíveis', () => {
  assert.throws(
    () => selectPlannerCandidate([
      {
        group_name: 'ReqSys DEV A',
        plan_name: 'WSJF DEV',
        plan_id: 'plan-a',
        bucket_id: 'bucket-a',
      },
      {
        group_name: 'ReqSys DEV B',
        plan_name: 'WSJF DEV',
        plan_id: 'plan-b',
        bucket_id: 'bucket-b',
      },
    ]),
    /descoberta_wsjf_ambigua:total=2:dev=2/,
  )
})

test('aceita janela de 900 s para atravessar o polling real do Planner', () => {
  assert.equal(validatePollTimeout('900'), 900)
})

test('rejeita janela acima do teto operacional', () => {
  assert.throws(() => validatePollTimeout('1201'), /poll_timeout_invalido:1201/)
})
