import assert from 'node:assert/strict'
import test from 'node:test'

import {
  applyRefreshToken,
  pollDecision,
} from '../scripts/msal_device_code_complete.mjs'

test('atualiza refresh token existente sem duplicar entrada', () => {
  const original = {
    schemaVersion: 1,
    sessionStorage: [
      { name: 'tema', value: 'dark' },
      {
        name: 'msal-refreshtoken',
        value: JSON.stringify({
          credentialType: 'RefreshToken',
          clientId: 'client-1',
          secret: 'segredo-antigo',
          expiresOn: 1,
        }),
      },
    ],
  }

  const updated = applyRefreshToken(original, { refresh_token: 'segredo-novo' }, 'client-1')
  const refreshEntries = updated.sessionStorage
    .map((entry) => {
      try { return JSON.parse(entry.value) } catch { return null }
    })
    .filter((entry) => entry?.credentialType === 'RefreshToken')

  assert.equal(refreshEntries.length, 1)
  assert.equal(refreshEntries[0].secret, 'segredo-novo')
  assert.equal(refreshEntries[0].clientId, 'client-1')
  assert.equal('expiresOn' in refreshEntries[0], false)
  assert.equal(updated.authSource, 'device_code')
  assert.equal(JSON.stringify(updated).includes('segredo-antigo'), false)
})

test('cria entrada de refresh token quando bundle não contém uma', () => {
  const updated = applyRefreshToken(
    { schemaVersion: 1, sessionStorage: [{ name: 'preferencia', value: 'true' }] },
    { refresh_token: 'rt-mobile' },
    'client-mobile',
  )

  const created = updated.sessionStorage.find((entry) => String(entry.name).startsWith('device-code-refreshtoken-'))
  assert.ok(created)
  const payload = JSON.parse(created.value)
  assert.equal(payload.credentialType, 'RefreshToken')
  assert.equal(payload.clientId, 'client-mobile')
  assert.equal(payload.secret, 'rt-mobile')
})

test('remove JSON válido não objeto e entradas externas malformadas antes do backend', () => {
  const updated = applyRefreshToken(
    {
      schemaVersion: 1,
      sessionStorage: [
        { name: 'objeto-valido', value: JSON.stringify({ cache: 'ok' }) },
        { name: 'booleano', value: 'true' },
        { name: 'numero', value: '123' },
        { name: 'lista', value: '[1,2,3]' },
        { name: 'nulo', value: 'null' },
        { name: 'texto-nao-json', value: 'dark' },
        'entrada-externa-invalida',
        ['lista-externa-invalida'],
      ],
    },
    { refresh_token: 'rt-mobile' },
    'client-mobile',
  )

  const names = updated.sessionStorage.map((entry) => entry.name)
  assert.deepEqual(names.sort(), [
    'device-code-refreshtoken-client-mobile',
    'objeto-valido',
    'texto-nao-json',
  ].sort())
  assert.equal(updated.sessionStorage.some((entry) => entry.name === 'booleano'), false)
  assert.equal(updated.sessionStorage.some((entry) => entry.name === 'lista'), false)
  assert.equal(updated.sessionStorage.some((entry) => entry.name === 'nulo'), false)
})

test('falha fechada quando resposta não contém refresh token', () => {
  assert.throws(
    () => applyRefreshToken({ sessionStorage: [] }, { access_token: 'somente-access' }, 'client-1'),
    /device_code_refresh_token_ausente/,
  )
})

test('classifica respostas de polling sem depender do texto de erro', () => {
  assert.equal(pollDecision({}, 200), 'success')
  assert.equal(pollDecision({ error: 'authorization_pending' }, 400), 'retry')
  assert.equal(pollDecision({ error: 'slow_down' }, 400), 'slow_down')
  assert.equal(pollDecision({ error: 'authorization_declined' }, 400), 'declined')
  assert.equal(pollDecision({ error: 'expired_token' }, 400), 'expired')
  assert.equal(pollDecision({ error: 'invalid_grant' }, 400), 'failure')
})
