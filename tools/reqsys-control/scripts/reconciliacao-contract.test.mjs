import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Script } from 'node:vm';
const html = readFileSync(new URL('../public/reconciliacao/index.html', import.meta.url), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/i)?.[1];
test('script demonstrativo tem sintaxe válida', () => {
  assert.ok(script, 'script ausente');
  assert.doesNotThrow(() => new Script(script));
});
test('não consulta serviços nem executa comandos externos', () => {
  assert.doesNotMatch(script, /\bfetch\s*\(|XMLHttpRequest\s*\(|sendBeacon\s*\(|WebSocket\s*\(/);
  assert.doesNotMatch(html, /<script\b[^>]+\bsrc\s*=/i);
});
test('alarmes e bloqueios operacionais visíveis', () => {
  for(const term of ['SHA divergente','Redmine','TODO Global','GitHub','SESSION_LAUNCH_OK','ETAPA BLOQUEADA']) assert.ok(html.includes(term),term);
});
test('importação exige confirmação e bloqueia registros duplicados', () => {
  for (const term of ['file.size>1024*1024','ids.has(d.id)','confirm(']) assert.ok(html.includes(term),term);
});
test('exemplos não são provas e não expõem tokens', () => {
  assert.ok(html.includes('AMBIENTE DEMONSTRATIVO'));
  assert.ok(html.includes('Nenhuma fonte externa foi consultada'));
  assert.doesNotMatch(html, /\b(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})\b/);
});