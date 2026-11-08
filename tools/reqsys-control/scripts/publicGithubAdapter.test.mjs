import assert from 'node:assert/strict';
import test from 'node:test';
import { APPROVED_SOURCES, readPublicIssue, sourceLink } from '../src/publicGithubAdapter.mjs';

const target = APPROVED_SOURCES[0];
const body = (changes = {}) => ({
  number: target.issue,
  title: 'Validação E2E',
  state: 'open',
  updated_at: '2026-11-08T10:30:00Z',
  html_url: sourceLink(target),
  ...changes,
});
const signal = new AbortController().signal;
function responder(data, status = 200) {
  return async (_url, init) => {
    assert.equal(init.method, 'GET');
    assert.equal(init.redirect, 'error');
    assert.equal(init.cache, 'no-store');
    assert.equal(init.signal, signal);
    assert.equal(init.headers.Accept, 'application/vnd.github+json');
    return { ok: status >= 200 && status < 300, status, json: async () => data };
  };
}
test('lê uma issue pública exata sem mutação', async () => {
  const result = await readPublicIssue(target, responder(body()), signal, () => '2026-11-08T10:40:00Z');
  assert.equal(result.state, 'open');
  assert.equal(result.title, 'Validação E2E');
  assert.equal(result.checked, '2026-11-08T10:40:00Z');
});
test('replay é leitura sem efeito e sem duplicação', async () => {
  let count = 0;
  const fetcher = async (url, init) => { count++; return responder(body())(url, init); };
  assert.deepEqual(await readPublicIssue(target, fetcher, signal), await readPublicIssue(target, fetcher, signal));
  assert.equal(count, 2);
});
test('rejeita URL/repositorio/issue fora da allowlist antes de fetch', async () => {
  let count = 0;
  await assert.rejects(readPublicIssue({ repository: 'privado', issue: 1 }, async () => { count++; }, signal), /não autorizada/);
  assert.equal(count, 0);
});
test('não aceita payload de PR ou issue com identidade divergente', async () => {
  await assert.rejects(readPublicIssue(target, responder(body({ pull_request: {} })), signal), /contrato/);
  await assert.rejects(readPublicIssue(target, responder(body({ html_url: 'https://evil.invalid' })), signal), /contrato/);
  await assert.rejects(readPublicIssue(target, responder(body({ number: 999 })), signal), /contrato/);
});
test('erro, quota, JSON inválido e datas inválidas falham fechado', async () => {
  await assert.rejects(readPublicIssue(target, responder({}, 403), signal), /limitada/);
  await assert.rejects(readPublicIssue(target, responder({}, 500), signal), /indisponível/);
  await assert.rejects(readPublicIssue(target, responder(body({ updated_at: 'invalido' })), signal), /contrato/);
  await assert.rejects(readPublicIssue(target, async () => ({ ok: true, json: async () => { throw Error('bad'); } }), signal), /JSON inválida/);
});
