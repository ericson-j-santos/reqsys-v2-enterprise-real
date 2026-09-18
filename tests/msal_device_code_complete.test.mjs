import assert from 'node:assert/strict'
import test from 'node:test'

import {
  MAX_DEVICE_CODE_ATTEMPTS,
  applyRefreshToken,
  authorizeWithRenewal,
  pollDecision,
} from '../scripts/msal_device_code_complete.mjs'
import {
  authorizationInstruction,
  pendingPayload,
  totalWaitSeconds,
  waitSecondsFromMinutes,
} from '../scripts/msal_device_code.mjs'

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

function fakeClock(startMs = 0) {
  let current = startMs
  return {
    now: () => current,
    advance: (ms) => { current += ms },
    sleep: async (ms) => { current += ms },
  }
}

function tokenResponse(payload, status = 200) {
  return { status, json: async () => payload }
}

test('renova o device code quando o código expira e mantém a janela humana aberta', async () => {
  const clock = fakeClock(Date.parse('2026-09-17T00:00:00Z'))
  const device = {
    client_id: 'client-1',
    device_code: 'dc-1',
    expires_in: 900,
    interval: 5,
    generated_at: new Date(clock.now()).toISOString(),
  }
  const renewed = []
  let polls = 0

  const result = await authorizeWithRenewal({
    tenantId: 'tenant',
    device,
    totalDeadline: clock.now() + 2400 * 1000,
    now: clock.now,
    sleepImpl: clock.sleep,
    fetchImpl: async () => {
      polls += 1
      if (polls === 1) return tokenResponse({ error: 'authorization_pending' }, 400)
      if (polls === 2) return tokenResponse({ error: 'expired_token' }, 400)
      return tokenResponse({ access_token: 'at', refresh_token: 'rt' }, 200)
    },
    requestDeviceCodeImpl: async ({ clientId }) => ({
      client_id: clientId,
      device_code: 'dc-2',
      user_code: 'CODIGO-2',
      verification_uri: 'https://microsoft.com/devicelogin',
      expires_in: 900,
      interval: 5,
      generated_at: new Date(clock.now()).toISOString(),
    }),
    onRenewedDeviceCode: async (next, attempt) => { renewed.push({ userCode: next.user_code, attempt }) },
  })

  assert.equal(result.tokenPayload.refresh_token, 'rt')
  assert.equal(result.attempt, 2)
  assert.deepEqual(renewed, [{ userCode: 'CODIGO-2', attempt: 2 }])
  assert.equal(result.device.device_code, 'dc-2')
})

test('renova o device code quando a validade do código termina antes do orçamento', async () => {
  const start = Date.parse('2026-09-17T00:00:00Z')
  const clock = fakeClock(start)
  const device = {
    client_id: 'client-1',
    device_code: 'dc-1',
    expires_in: 60,
    interval: 5,
    generated_at: new Date(start).toISOString(),
  }
  let requested = 0

  const result = await authorizeWithRenewal({
    tenantId: 'tenant',
    device,
    totalDeadline: start + 900 * 1000,
    now: clock.now,
    sleepImpl: clock.sleep,
    fetchImpl: async () => tokenResponse(
      requested === 0 ? { error: 'authorization_pending' } : { access_token: 'at', refresh_token: 'rt' },
      requested === 0 ? 400 : 200,
    ),
    requestDeviceCodeImpl: async ({ clientId }) => {
      requested += 1
      return {
        client_id: clientId,
        device_code: `dc-${requested + 1}`,
        user_code: `CODIGO-${requested + 1}`,
        verification_uri: 'https://microsoft.com/devicelogin',
        expires_in: 900,
        interval: 5,
        generated_at: new Date(clock.now()).toISOString(),
      }
    },
  })

  assert.equal(requested, 1)
  assert.equal(result.tokenPayload.access_token, 'at')
})

test('falha fechada ao esgotar o orçamento total sem autorização', async () => {
  const start = Date.parse('2026-09-17T00:00:00Z')
  const clock = fakeClock(start)

  await assert.rejects(
    authorizeWithRenewal({
      tenantId: 'tenant',
      device: {
        client_id: 'client-1',
        device_code: 'dc-1',
        expires_in: 900,
        interval: 5,
        generated_at: new Date(start).toISOString(),
      },
      totalDeadline: start + 300 * 1000,
      now: clock.now,
      sleepImpl: clock.sleep,
      fetchImpl: async () => tokenResponse({ error: 'authorization_pending' }, 400),
      requestDeviceCodeImpl: async () => { throw new Error('nao_deveria_renovar') },
    }),
    /device_code_expirado_sem_autorizacao/,
  )
})

test('recusa explícita não é reciclada como renovação', async () => {
  const start = Date.parse('2026-09-17T00:00:00Z')
  const clock = fakeClock(start)

  await assert.rejects(
    authorizeWithRenewal({
      tenantId: 'tenant',
      device: {
        client_id: 'client-1',
        device_code: 'dc-1',
        expires_in: 900,
        interval: 5,
        generated_at: new Date(start).toISOString(),
      },
      totalDeadline: start + 1800 * 1000,
      now: clock.now,
      sleepImpl: clock.sleep,
      fetchImpl: async () => tokenResponse({ error: 'authorization_declined' }, 400),
      requestDeviceCodeImpl: async () => { throw new Error('nao_deveria_renovar') },
    }),
    /device_code_autorizacao_recusada/,
  )
})

test('limita o número de renovações mesmo com orçamento restante', async () => {
  const start = Date.parse('2026-09-17T00:00:00Z')
  const clock = fakeClock(start)
  let requested = 0

  await assert.rejects(
    authorizeWithRenewal({
      tenantId: 'tenant',
      device: {
        client_id: 'client-1',
        device_code: 'dc-1',
        expires_in: 60,
        interval: 5,
        generated_at: new Date(start).toISOString(),
      },
      totalDeadline: start + MAX_DEVICE_CODE_ATTEMPTS * 3600 * 1000,
      now: clock.now,
      sleepImpl: clock.sleep,
      fetchImpl: async () => tokenResponse({ error: 'authorization_pending' }, 400),
      requestDeviceCodeImpl: async ({ clientId }) => {
        requested += 1
        return {
          client_id: clientId,
          device_code: `dc-${requested + 1}`,
          user_code: `CODIGO-${requested + 1}`,
          verification_uri: 'https://microsoft.com/devicelogin',
          expires_in: 60,
          interval: 5,
          generated_at: new Date(clock.now()).toISOString(),
        }
      },
    }),
    /device_code_expirado_sem_autorizacao/,
  )

  assert.equal(requested, MAX_DEVICE_CODE_ATTEMPTS - 1)
})

test('orçamento total é normalizado dentro dos limites suportados', () => {
  assert.equal(totalWaitSeconds(''), 900)
  assert.equal(totalWaitSeconds('abc'), 900)
  assert.equal(totalWaitSeconds('60'), 300)
  assert.equal(totalWaitSeconds('1500'), 1500)
  assert.equal(totalWaitSeconds('99999'), 3000)
})

test('instrução de autorização não expõe o device code privado', () => {
  const device = {
    device_code: 'segredo-device-code',
    user_code: 'PUBLICO-1',
    verification_uri: 'https://microsoft.com/devicelogin',
  }
  const payload = JSON.stringify(pendingPayload(device, 3))
  const instruction = authorizationInstruction(device, 3)

  assert.equal(payload.includes('segredo-device-code'), false)
  assert.equal(instruction.includes('segredo-device-code'), false)
  assert.match(instruction, /PUBLICO-1/)
  assert.match(instruction, /tentativa 3/)
  assert.equal(JSON.parse(payload).attempt, 3)
})

test('orçamento em minutos é convertido e limitado', () => {
  assert.equal(waitSecondsFromMinutes(''), 900)
  assert.equal(waitSecondsFromMinutes('0'), 900)
  assert.equal(waitSecondsFromMinutes('25'), 1500)
  assert.equal(waitSecondsFromMinutes('1'), 300)
  assert.equal(waitSecondsFromMinutes('600'), 3000)
})
