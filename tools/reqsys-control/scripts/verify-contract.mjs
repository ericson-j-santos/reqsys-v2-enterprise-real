import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const main = read('../src/ReqSysDashboard.tsx');
const feed = read('../src/PublicGithubReadOnly.tsx');
const adapter = read('../src/publicGithubAdapter.mjs');
const tests = JSON.parse(read('../tests/tests.json'));
const targets = [...adapter.matchAll(/repository: '([^']+)', issue: (\d+)/g)];
assert.equal(targets.length, 5);
assert.equal(new Set(targets.map(v => v[1] + '/' + v[2])).size, 5);
// Compara a declaração completa do origin: prefixos/sufixos maliciosos não passam.
function assertExactOrigin(source, symbol, expectedUrl) {
  const declarations = source.split(/\r?\n/).filter(line => line.startsWith(`const ${symbol} = `));
  assert.deepEqual(declarations, [`const ${symbol} = '${expectedUrl}';`]);
}
const trustedApi = 'https://api.github.com/repos/ericson-j-santos';
assertExactOrigin(adapter, 'ORIGIN', trustedApi);
assertExactOrigin(adapter, 'HTML_ORIGIN', 'https://github.com/ericson-j-santos');
// Negativos obrigatórios: host semelhante e sufixo hostil falham fechado.
const originDeclaration = `const ORIGIN = '${trustedApi}';`;
for (const hostileUrl of [
  'https://api.github.com.evil.invalid/repos/ericson-j-santos',
  'https://api.github.com/repos/ericson-j-santos.evil.invalid',
]) {
  const changed = adapter.replace(originDeclaration, `const ORIGIN = '${hostileUrl}';`);
  assert.notEqual(changed, adapter);
  assert.throws(() => assertExactOrigin(changed, 'ORIGIN', trustedApi));
}
assert.match(adapter, /cache: 'no-store'/);
assert.match(adapter, /if \(!response\?\.ok\)/);
assert.match(adapter, /data\.number !== source\.issue/);
assert.match(feed, /controller\.abort\(\), 10000/);
assert.doesNotMatch(adapter + feed, /method:\s*['"](?:POST|PUT|PATCH|DELETE)/);
assert.doesNotMatch(main + feed + adapter, /\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b/);
assert.match(main, /ready_for_work é sempre false/);
assert.match(main, /Badge tone="danger">ready_for_work = false/);
assert.match(main, /PublicGithubReadOnly/);
assert.match(feed, /readPublicIssue\(target, fetch, signal\)/);
assert.equal(tests.length, 5);
assert.equal(tests.filter(t => t.sanity).length, 1);
assert.ok(tests.every(t => t.covers?.length && t.steps?.length && t.description));
console.log('Contratos estáticos: OK (sem autorização de host/sem escrita externa)');
