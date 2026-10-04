const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const { test, expect } = require('@playwright/test')

const SERVICE_ID = process.env.RSM_UI_SERVICE_ID
const EXPECTED_SHA = process.env.RSM_EXPECTED_SHA
const EVIDENCE_PATH = process.env.RSM_UI_EVIDENCE_PATH || '../artifacts/rsm/rsm-service-case-ui-browser.json'

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex')
}

async function loginAdmin(request) {
  const response = await request.post('/api/v1/auth/login', {
    data: { email: 'rsm-e2e@example.com' },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return (await response.json()).data
}

async function createCase(request, token, idempotencyKey, correlationId) {
  const response = await request.post('/api/v1/service-cases', {
    headers: {
      Authorization: `Bearer ${token}`,
      'X-Correlation-ID': correlationId,
    },
    data: {
      case_type: 'REQUEST',
      service_id: SERVICE_ID,
      requester: 'rsm-ui-e2e',
      impact: 'MEDIUM',
      urgency: 'HIGH',
      idempotency_key: idempotencyKey,
      event_id: crypto.randomUUID(),
      source: 'reqsys',
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return (await response.json()).data.case
}

async function transitionByApi(request, token, serviceCase, targetState, correlationId) {
  const response = await request.post(`/api/v1/service-cases/${serviceCase.case_id}/transitions`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'X-Correlation-ID': correlationId,
    },
    data: {
      target_state: targetState,
      expected_version: serviceCase.version,
      event_id: crypto.randomUUID(),
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return (await response.json()).data.case
}

async function installSession(page, login) {
  await page.addInitScript(({ token, usuario }) => {
    localStorage.setItem('reqsys_token', token)
    localStorage.setItem('reqsys_usuario', JSON.stringify(usuario))
  }, { token: login.access_token, usuario: login.usuario })
}

test('RSM-05 browser real confirma mutação e rejeição sem falso sucesso', async ({ page, request }) => {
  expect(SERVICE_ID).toBeTruthy()
  expect(EXPECTED_SHA).toMatch(/^[a-f0-9]{40}$/)

  const login = await loginAdmin(request)
  await installSession(page, login)

  const positiveCorrelation = `rsm05-ui-positive-${EXPECTED_SHA.slice(0, 12)}`
  const negativeCorrelation = `rsm05-ui-negative-${EXPECTED_SHA.slice(0, 12)}`
  const positiveKey = sha256(positiveCorrelation)
  const negativeKey = sha256(negativeCorrelation)

  const positive = await createCase(request, login.access_token, positiveKey, positiveCorrelation)

  await page.goto(`/service-cases/${positive.case_id}`)
  await expect(page.getByTestId('service-case-view')).toBeVisible()
  await expect(page.getByTestId('service-case-state')).toContainText('Novo')
  await expect(page.getByTestId('transition-TRIAGE')).toBeVisible()
  await expect(page.getByTestId('transition-CLOSED')).toHaveCount(0)

  await page.getByTestId('transition-TRIAGE').click()
  await expect(page.getByTestId('service-case-success')).toContainText('Estado persistido confirmado')
  await expect(page.getByTestId('service-case-state')).toContainText('Triagem')

  let negative = await createCase(request, login.access_token, negativeKey, negativeCorrelation)
  negative = await transitionByApi(request, login.access_token, negative, 'TRIAGE', negativeCorrelation)
  negative = await transitionByApi(request, login.access_token, negative, 'PENDING_APPROVAL', negativeCorrelation)

  await page.goto(`/service-cases/${negative.case_id}`)
  await expect(page.getByTestId('service-case-state')).toContainText('Aguardando aprovação')
  await expect(page.getByTestId('transition-IN_PROGRESS')).toBeVisible()

  await page.getByTestId('transition-IN_PROGRESS').click()
  await expect(page.getByTestId('service-case-error')).toContainText('aprovação')
  await expect(page.getByTestId('service-case-state')).toContainText('Aguardando aprovação')
  await expect(page.getByTestId('service-case-success')).toHaveCount(0)

  const evidence = {
    status: 'browser_passed',
    expected_sha: EXPECTED_SHA,
    positive: {
      case_id: positive.case_id,
      idempotency_key: positiveKey,
      correlation_id: positiveCorrelation,
      expected_state: 'TRIAGE',
    },
    negative: {
      case_id: negative.case_id,
      idempotency_key: negativeKey,
      correlation_id: negativeCorrelation,
      expected_state: 'PENDING_APPROVAL',
      rejected_target: 'IN_PROGRESS',
    },
  }
  fs.mkdirSync(path.dirname(EVIDENCE_PATH), { recursive: true })
  fs.writeFileSync(EVIDENCE_PATH, JSON.stringify(evidence, null, 2) + '\n', 'utf8')
})
