const test = require('node:test')
const assert = require('node:assert/strict')
const { sanitizeStorageState } = require('./msal-storage-state-sanitizer.cjs')

test('remove sessao efemera ReqSys e preserva dados independentes', () => {
  const source = {
    cookies: [{ name: 'cookie-ok', value: '1' }],
    origins: [
      { origin: 'https://reqsys-app-dev.fly.dev', localStorage: [
        { name: 'reqsys_token', value: 'stale' },
        { name: 'reqsys_usuario', value: '{"nome":"Teste"}' },
        { name: 'reqsys_tema_visual', value: 'figmaPadraoOuro' },
      ]},
      { origin: 'https://outro.example', localStorage: [{ name: 'reqsys_token', value: 'nao-tocar' }] },
    ],
  }
  const clean = sanitizeStorageState(source, 'https://reqsys-app-dev.fly.dev')
  assert.deepEqual(clean.origins[0].localStorage, [{ name: 'reqsys_tema_visual', value: 'figmaPadraoOuro' }])
  assert.equal(clean.origins[1].localStorage[0].value, 'nao-tocar')
  assert.equal(source.origins[0].localStorage.length, 3)
  assert.deepEqual(clean.cookies, source.cookies)
})
