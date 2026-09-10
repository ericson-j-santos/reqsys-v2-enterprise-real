import test from 'node:test'
import assert from 'node:assert/strict'

import {
  evaluateContract,
  filterMessagesSince,
  messageContainsTitle,
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
