const test = require('node:test');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const net = require('node:net');
const path = require('node:path');

const servidorPath = path.resolve(__dirname, '..', 'src', 'servidor-simulado.js');
let servidor;
let processarDemanda;

function obterPortaLivre() {
  return new Promise((resolve, reject) => {
    const temporario = net.createServer();
    temporario.once('error', reject);
    temporario.listen(0, '127.0.0.1', () => {
      const porta = temporario.address().port;
      temporario.close(() => resolve(porta));
    });
  });
}

test.before(async () => {
  const porta = await obterPortaLivre();
  process.env.API_BASE_URL = `http://127.0.0.1:${porta}`;
  servidor = spawn(process.execPath, [servidorPath], {stdio: 'ignore', env: {...process.env, PORT: String(porta)}});
  await new Promise(resolve => setTimeout(resolve, 250));
  ({processarDemanda} = require('../src/executar-fluxo'));
});
test.after(() => servidor.kill());

test('cria dossiê com dados sintéticos', async () => {
  const resultado = await processarDemanda({demanda_id:'DEM-TESTE-01', tipo_servico:'TREINO', data_referencia:'2026-08-10', simular_falha:false});
  assert.equal(resultado.situacao, 'DOSSIÊ_CRIADO');
  assert.match(resultado.dossie_id, /^DOS-[A-F0-9]{12}$/);
  assert.ok(resultado.correlation_id);
});

test('registra recusa de regra de negócio', async () => {
  const resultado = await processarDemanda({demanda_id:'DEM-TESTE-02', tipo_servico:'TREINO', data_referencia:'2026-08-10', simular_falha:true});
  assert.equal(resultado.situacao, 'CRIAÇÃO_RECUSADA');
  assert.equal(resultado.status_http, 422);
});
