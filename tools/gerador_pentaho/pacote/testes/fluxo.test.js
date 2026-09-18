const test = require('node:test');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const http = require('node:http');
const net = require('node:net');
const path = require('node:path');

const servidorPath = path.resolve(__dirname, '..', 'src', 'servidor-simulado.js');
const modulePath = require.resolve('../src/executar-fluxo');
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

function responderJson(res, status, corpo) {
  res.writeHead(status, {'content-type': 'application/json; charset=utf-8'});
  res.end(JSON.stringify(corpo));
}

// Servidor HTTP descartável para cenários que o servidor-simulado.js compartilhado
// não reproduz (5xx intermitente/persistente, credencial recusada em isolamento).
// Mantém servidor-simulado.js fiel apenas ao contrato observável da API real.
function criarServidorHttp(handler) {
  return new Promise((resolve, reject) => {
    const servidorHttp = http.createServer(handler);
    servidorHttp.once('error', reject);
    servidorHttp.listen(0, '127.0.0.1', () => {
      resolve({
        porta: servidorHttp.address().port,
        fechar: () => new Promise(res => servidorHttp.close(res))
      });
    });
  });
}

// `configuracao` (API_BASE_URL/CLIENT_ID/MAX_TENTATIVAS/...) é lida uma única vez
// na carga do módulo. Para variar esses parâmetros por teste sem tocar no código de
// produção, recarrega o módulo com o cache invalidado sob env temporário.
function carregarModuloComEnv(overrides) {
  const originais = {};
  for (const chave of Object.keys(overrides)) {
    originais[chave] = process.env[chave];
    process.env[chave] = overrides[chave];
  }
  delete require.cache[modulePath];
  const modulo = require('../src/executar-fluxo');
  return {
    modulo,
    restaurar() {
      for (const chave of Object.keys(overrides)) {
        if (originais[chave] === undefined) delete process.env[chave];
        else process.env[chave] = originais[chave];
      }
      delete require.cache[modulePath];
    }
  };
}

test.before(async () => {
  const porta = await obterPortaLivre();
  process.env.API_BASE_URL = `http://127.0.0.1:${porta}`;
  servidor = spawn(process.execPath, [servidorPath], {stdio: 'ignore', env: {...process.env, PORT: String(porta)}});
  await new Promise(resolve => setTimeout(resolve, 250));
  ({processarDemanda} = require('../src/executar-fluxo'));
});
test.after(() => servidor.kill());

test('cria dossiê com dados sintéticos (DOSSIÊ_CRIADO)', async () => {
  const resultado = await processarDemanda({demanda_id:'DEM-TESTE-01', tipo_servico:'TREINO', data_referencia:'2026-08-10', simular_falha:false});
  assert.equal(resultado.situacao, 'DOSSIÊ_CRIADO');
  assert.match(resultado.dossie_id, /^DOS-[A-F0-9]{12}$/);
  assert.ok(resultado.correlation_id);
});

test('registra recusa de regra de negócio (CRIAÇÃO_RECUSADA)', async () => {
  const resultado = await processarDemanda({demanda_id:'DEM-TESTE-02', tipo_servico:'TREINO', data_referencia:'2026-08-10', simular_falha:true});
  assert.equal(resultado.situacao, 'CRIAÇÃO_RECUSADA');
  assert.equal(resultado.status_http, 422);
});

test('não repete automaticamente erro 4xx (fail-fast, critério de aceite)', async () => {
  let chamadasDossie = 0;
  const servidorLocal = await criarServidorHttp((req, res) => {
    if (req.url === '/oauth/token') return responderJson(res, 200, {access_token: 'mock-token-teste', token_type: 'Bearer', expires_in: 300});
    if (req.url === '/v1/dossies') { chamadasDossie += 1; return responderJson(res, 422, {codigo: 'REGRA_NEGOCIO_RECUSADA'}); }
    responderJson(res, 404, {});
  });
  const {modulo, restaurar} = carregarModuloComEnv({API_BASE_URL: `http://127.0.0.1:${servidorLocal.porta}`});
  try {
    const resultado = await modulo.processarDemanda({demanda_id:'DEM-4XX-01', tipo_servico:'TREINO', data_referencia:'2026-08-10'});
    assert.equal(resultado.situacao, 'CRIAÇÃO_RECUSADA');
    assert.equal(chamadasDossie, 1, 'erro 4xx não deve ser retentado automaticamente');
  } finally {
    restaurar();
    await servidorLocal.fechar();
  }
});

test('repete em 5xx intermitente e sucede antes de esgotar tentativas', async () => {
  let chamadasDossie = 0;
  const servidorLocal = await criarServidorHttp((req, res) => {
    if (req.url === '/oauth/token') return responderJson(res, 200, {access_token: 'mock-token-teste', token_type: 'Bearer', expires_in: 300});
    if (req.url === '/v1/dossies') {
      chamadasDossie += 1;
      if (chamadasDossie < 2) return responderJson(res, 500, {codigo: 'INDISPONIVEL_TEMPORARIO'});
      return responderJson(res, 201, {dossie_id: 'DOS-RETRY-OK', situacao: 'CRIADO'});
    }
    responderJson(res, 404, {});
  });
  const {modulo, restaurar} = carregarModuloComEnv({API_BASE_URL: `http://127.0.0.1:${servidorLocal.porta}`});
  try {
    const resultado = await modulo.processarDemanda({demanda_id:'DEM-RETRY-01', tipo_servico:'TREINO', data_referencia:'2026-08-10'});
    assert.equal(resultado.situacao, 'DOSSIÊ_CRIADO');
    assert.equal(chamadasDossie, 2);
  } finally {
    restaurar();
    await servidorLocal.fechar();
  }
});

test('esgota tentativas em 5xx persistente e finaliza como RESPOSTA_INVÁLIDA', async () => {
  let chamadasDossie = 0;
  const servidorLocal = await criarServidorHttp((req, res) => {
    if (req.url === '/oauth/token') return responderJson(res, 200, {access_token: 'mock-token-teste', token_type: 'Bearer', expires_in: 300});
    if (req.url === '/v1/dossies') { chamadasDossie += 1; return responderJson(res, 503, {codigo: 'INDISPONIVEL'}); }
    responderJson(res, 404, {});
  });
  const {modulo, restaurar} = carregarModuloComEnv({API_BASE_URL: `http://127.0.0.1:${servidorLocal.porta}`, MAX_TENTATIVAS: '3'});
  try {
    const resultado = await modulo.processarDemanda({demanda_id:'DEM-5XX-01', tipo_servico:'TREINO', data_referencia:'2026-08-10'});
    assert.equal(resultado.situacao, 'RESPOSTA_INVÁLIDA');
    assert.equal(resultado.status_http, 503);
    assert.equal(chamadasDossie, 3, 'deve respeitar MAX_TENTATIVAS e não insistir além do limite');
  } finally {
    restaurar();
    await servidorLocal.fechar();
  }
});

test('recusa autenticação com credencial inválida (AUTENTICAÇÃO_RECUSADA)', async () => {
  // Atribuição direta (não via objeto de overrides) para que a variável de
  // ambiente CLIENT_ID fique claramente identificável como configuração de
  // runtime sintética de teste, não como client_id fixo no código-fonte.
  const clientIdOriginal = process.env.CLIENT_ID;
  process.env.CLIENT_ID = 'cliente-invalido';
  delete require.cache[modulePath];
  const modulo = require('../src/executar-fluxo');
  try {
    const resultado = await modulo.processarDemanda({demanda_id:'DEM-AUTH-01', tipo_servico:'TREINO', data_referencia:'2026-08-10'});
    assert.equal(resultado.situacao, 'AUTENTICAÇÃO_RECUSADA');
    assert.equal(resultado.status_http, 401);
  } finally {
    if (clientIdOriginal === undefined) delete process.env.CLIENT_ID;
    else process.env.CLIENT_ID = clientIdOriginal;
    delete require.cache[modulePath];
  }
});

test('recusa entrada inválida antes de qualquer chamada de rede (FALHA_TÉCNICA)', async () => {
  const resultado = await processarDemanda({demanda_id:'', tipo_servico:'TREINO', data_referencia:'2026-08-10'});
  assert.equal(resultado.situacao, 'FALHA_TÉCNICA');
  assert.equal(resultado.status_http, null);
  assert.equal(resultado.codigo_erro, 'CAMPO_INVALIDO:demanda_id');
});

test('falha técnica quando o serviço está indisponível (conexão recusada, retentativas esgotadas)', async () => {
  const portaFechada = await obterPortaLivre();
  const {modulo, restaurar} = carregarModuloComEnv({
    API_BASE_URL: `http://127.0.0.1:${portaFechada}`,
    MAX_TENTATIVAS: '2',
    TIMEOUT_MS: '500'
  });
  try {
    const resultado = await modulo.processarDemanda({demanda_id:'DEM-INDISP-01', tipo_servico:'TREINO', data_referencia:'2026-08-10'});
    assert.equal(resultado.situacao, 'FALHA_TÉCNICA');
    assert.ok(resultado.codigo_erro, 'deve carregar o motivo técnico da falha para evidência/auditoria');
  } finally {
    restaurar();
  }
});
