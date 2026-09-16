import test from 'node:test'
import assert from 'node:assert/strict'

import {
  sanitizedGateSummary,
  selectGateArtifact,
  shouldRerun,
  validateUserCode,
  validateVerificationUri,
} from '../scripts/pc24x7_microsoft_auth_gate_agent.mjs'

test('aceita somente verification_uri HTTPS da Microsoft', () => {
  assert.match(validateVerificationUri('https://microsoft.com/devicelogin'), /^https:\/\/microsoft\.com\//)
  assert.match(validateVerificationUri('https://login.microsoftonline.com/common/oauth2/deviceauth'), /^https:\/\/login\.microsoftonline\.com\//)
  assert.throws(() => validateVerificationUri('http://microsoft.com/devicelogin'), /protocolo_invalido/)
  assert.throws(() => validateVerificationUri('https://example.com/devicelogin'), /host_nao_permitido/)
})

test('valida user_code sem aceitar texto arbitrario', () => {
  assert.equal(validateUserCode('ABCD-EFGH'), 'ABCD-EFGH')
  assert.throws(() => validateUserCode('abc def ghi'), /formato_invalido/)
  assert.throws(() => validateUserCode(''), /formato_invalido/)
})

test('seleciona somente o artifact valido mais recente', () => {
  const artifacts = [
    { id: 1, name: 'planner-teams-connection-reference-device-login-1-attempt-1', expired: false, created_at: '2026-09-16T18:00:00Z' },
    { id: 2, name: 'planner-teams-connection-reference-device-login-1-attempt-2', expired: false, created_at: '2026-09-16T18:05:00Z' },
    { id: 3, name: 'planner-teams-connection-reference-device-login-1-attempt-3', expired: true, created_at: '2026-09-16T18:10:00Z' },
  ]
  assert.equal(selectGateArtifact(artifacts)?.id, 2)
})

test('rerun automatico fica limitado a falha com gate humano pendente', () => {
  const run = { status: 'completed', conclusion: 'failure' }
  assert.equal(shouldRerun(run, { required: true }, 0, 1), true)
  assert.equal(shouldRerun(run, { required: true }, 1, 1), false)
  assert.equal(shouldRerun({ status: 'completed', conclusion: 'success' }, { required: true }, 0, 1), false)
  assert.equal(shouldRerun(run, { required: false }, 0, 1), false)
})

test('resumo sanitizado nao persiste user_code', () => {
  const summary = sanitizedGateSummary({
    required: true,
    status: 'awaiting_microsoft_authorization',
    verification_uri: 'https://microsoft.com/devicelogin',
    user_code: 'ABCD-EFGH',
    generated_at: '2026-09-16T18:00:00Z',
    expires_in_seconds: 900,
  }, 123, 'artifact')
  assert.equal(summary.user_code_present, true)
  assert.equal(Object.prototype.hasOwnProperty.call(summary, 'user_code'), false)
  assert.equal(summary.verification_host, 'microsoft.com')
})
