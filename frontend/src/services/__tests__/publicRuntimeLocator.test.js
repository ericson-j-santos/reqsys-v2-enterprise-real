import { beforeEach, describe, expect, it } from 'vitest'
import {
  isGitHubPagesDevRuntime,
  resetPublicRuntimeResolutionForTests,
  verifyLocatorEnvelope,
} from '../publicRuntimeLocator'

const config = {
  environment: 'dev',
  allowed_url_suffix: '.trycloudflare.com',
  required_runtime_contract: '2.0.0',
  required_endpoints: [
    '/api/health',
    '/api/runtime/health',
    '/api/runtime/readiness',
    '/api/runtime/build-info',
  ],
}

function bytesToBase64(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes)))
}

async function signedEnvelope(overrides = {}) {
  const keys = await crypto.subtle.generateKey({ name: 'Ed25519' }, true, ['sign', 'verify'])
  const publicKey = await crypto.subtle.exportKey('raw', keys.publicKey)
  const now = 1_800_000_000
  const payload = {
    environment: 'dev',
    issued_at: now - 30,
    expires_at: now + 600,
    selected_url: 'https://runtime-valid.trycloudflare.com',
    urls: ['https://runtime-valid.trycloudflare.com'],
    runtime_contract: {
      version: '2.0.0',
      required_endpoints: config.required_endpoints,
      static_frontend_required: true,
      vite_hmr_forbidden: true,
    },
    ...overrides,
  }
  const payloadB64 = bytesToBase64(new TextEncoder().encode(JSON.stringify(payload)))
  const signature = await crypto.subtle.sign(
    { name: 'Ed25519' },
    keys.privateKey,
    new TextEncoder().encode(payloadB64),
  )
  return {
    envelope: { v: 1, payload_b64: payloadB64, signature_b64: bytesToBase64(signature) },
    locatorConfig: { ...config, public_key_b64: bytesToBase64(publicKey) },
    now,
  }
}

describe('publicRuntimeLocator', () => {
  beforeEach(() => resetPublicRuntimeResolutionForTests())

  it('ativa somente no frontend DEV estável do GitHub Pages', () => {
    expect(isGitHubPagesDevRuntime({
      hostname: 'ericson-j-santos.github.io',
      pathname: '/reqsys-v2-enterprise-real/dev/login',
    })).toBe(true)
    expect(isGitHubPagesDevRuntime({ hostname: 'localhost', pathname: '/dev/' })).toBe(false)
  })

  it('aceita envelope Ed25519 vigente com contrato runtime completo', async () => {
    const { envelope, locatorConfig, now } = await signedEnvelope()
    const payload = await verifyLocatorEnvelope(envelope, locatorConfig, { now })
    expect(payload.selected_url).toBe('https://runtime-valid.trycloudflare.com')
  })

  it('usa verificação Ed25519 compatível quando o Web Crypto móvel não suporta o algoritmo', async () => {
    const { envelope, locatorConfig, now } = await signedEnvelope()
    const cryptoSemEd25519 = {
      subtle: {
        importKey: async () => { throw new DOMException('Algorithm not supported', 'NotSupportedError') },
      },
    }
    const payload = await verifyLocatorEnvelope(envelope, locatorConfig, {
      now,
      cryptoImpl: cryptoSemEd25519,
    })
    expect(payload.selected_url).toBe('https://runtime-valid.trycloudflare.com')
  })

  it('rejeita origem fora de trycloudflare mesmo com assinatura válida', async () => {
    const { envelope, locatorConfig, now } = await signedEnvelope({
      selected_url: 'https://evil.example.com',
      urls: ['https://evil.example.com'],
    })
    await expect(verifyLocatorEnvelope(envelope, locatorConfig, { now })).resolves.toBeNull()
  })

  it('rejeita locator expirado', async () => {
    const { envelope, locatorConfig, now } = await signedEnvelope({ expires_at: 1_799_999_999 })
    await expect(verifyLocatorEnvelope(envelope, locatorConfig, { now })).resolves.toBeNull()
  })
})
