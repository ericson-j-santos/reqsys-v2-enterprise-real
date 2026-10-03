import assert from 'node:assert/strict'
import test from 'node:test'

import { requireProviderNeutralHttpsUrl } from './runtime-url-policy.mjs'

test('aceita runtime HTTPS provider-neutral e normaliza barra final', () => {
  assert.equal(
    requireProviderNeutralHttpsUrl('https://reqsys.example.test/'),
    'https://reqsys.example.test',
  )
})

for (const url of [
  'https://fly.dev',
  'https://reqsys.fly.dev/login',
  'https://FLY.IO./app',
  'https://api.fly.io/v1',
]) {
  test(`recusa hostname Fly aposentado: ${url}`, () => {
    assert.throws(
      () => requireProviderNeutralHttpsUrl(url),
      /Fly\.io, retirado definitivamente/,
    )
  })
}

test('não confunde domínio semelhante com subdomínio Fly', () => {
  assert.equal(
    requireProviderNeutralHttpsUrl('https://fly.dev.example.test'),
    'https://fly.dev.example.test',
  )
})

test('recusa URL implícita e protocolo não HTTPS', () => {
  assert.throws(() => requireProviderNeutralHttpsUrl('reqsys.example.test'), /URL HTTPS explícita/)
  assert.throws(() => requireProviderNeutralHttpsUrl('http://reqsys.example.test'), /usar HTTPS/)
})
