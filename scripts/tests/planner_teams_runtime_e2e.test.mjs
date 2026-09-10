import test from 'node:test'
import assert from 'node:assert/strict'

import {
  evaluateContract,
  filterMessagesSince,
  messageContainsTitle,
  selectPlannerCandidate,
} from '../planner_teams_runtime_e2e.mjs'

test('aprova somente com controle normal presente e E2E ausente', () => {
  assert.deepEqual(
    evaluateContract({ normalFound: true, e2eFound: false }),
    { passed: true, reason: 'contract_satisfied' },
  )
})

test('reprova quando a tarefa E2E aparece no Teams', () => {
  assert.deepEqual(
    evaluateContract({ normalFound: true, e2eFound: true }),
    { passed: false, reason: 'ct01_e2e_message_observed' },
  )
})

test('reprova quando o controle normal nao aparece', () => {
  assert.deepEqual(
    evaluateContract({ normalFound: false, e2eFound: false }),
    { passed: false, reason: 'ct02_normal_message_not_observed' },
  )
})

test('encontra titulo em corpo ou attachment serializado', () => {
  const title = 'REQSYS-AUTOMATED-CONTROL-NORMAL-123'
  assert.equal(messageContainsTitle({ body: { content: `Tarefa: ${title}` } }, title), true)
  assert.equal(messageContainsTitle({ attachments: [{ content: JSON.stringify({ title }) }] }, title), true)
  assert.equal(messageContainsTitle({ body: { content: 'outra tarefa' } }, title), false)
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
