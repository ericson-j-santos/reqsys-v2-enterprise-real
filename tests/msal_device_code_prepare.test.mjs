import test from 'node:test'
import assert from 'node:assert/strict'

import {
  findRefresh,
  resolveDeviceClientId,
} from '../scripts/msal_device_code_prepare.mjs'

test('resolve bootstrap client id when session has no refresh token', () => {
  assert.equal(resolveDeviceClientId(null, 'dedicated-client'), 'dedicated-client')
})

test('existing refresh token remains the preferred client id', () => {
  assert.equal(resolveDeviceClientId({ clientId: 'session-client' }, 'dedicated-client'), 'session-client')
})

test('missing refresh and bootstrap identity fails closed', () => {
  assert.throws(
    () => resolveDeviceClientId(null, ''),
    /msal_refresh_token_ausente_sem_bootstrap_client_id/,
  )
})

test('findRefresh returns null for an empty bootstrap state', () => {
  assert.equal(findRefresh({ schemaVersion: 1, sessionStorage: [] }), null)
})

test('findRefresh reads the persisted compact token', () => {
  const bundle = {
    sessionStorage: [{
      name: 'device-code-refreshtoken-client',
      value: JSON.stringify({
        credentialType: 'RefreshToken',
        clientId: 'client',
        secret: 'not-real',
      }),
    }],
  }
  assert.equal(findRefresh(bundle)?.clientId, 'client')
})
