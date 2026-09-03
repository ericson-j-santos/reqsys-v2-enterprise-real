const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const configuracao = {
  apiBaseUrl: process.env.API_BASE_URL || 'http://127.0.0.1:8080',
  clientId: process.env.CLIENT_ID || 'cliente-treinamento',
  clientSecret: process.env.CLIENT_SECRET || 'segredo-exclusivo-de-treino',
  maxTentativas: Number(process.env.MAX_TENTATIVAS || 3),
  timeoutMs: Number(process.env.TIMEOUT_MS || 5000)
};

function validarDemanda(demanda) {
  for (const campo of ['demanda_id', 'tipo_servico', 'data_referencia']) {
    if (typeof demanda[campo] !== 'string' || !demanda[campo].trim()) throw new Error(`CAMPO_INVALIDO:${campo}`);
  }
}

async function chamar(url, opcoes, maxTentativas = 1) {
  let ultimoErro;
  for (let tentativa = 1; tentativa <= maxTentativas; tentativa++) {
    try {
      const resposta = await fetch(url, {...opcoes, signal: AbortSignal.timeout(configuracao.timeoutMs)});
      const corpo = await resposta.json().catch(() => ({}));
      if (resposta.status >= 500 && tentativa < maxTentativas) continue;
      return {status: resposta.status, corpo};
    } catch (erro) {
      ultimoErro = erro;
      if (tentativa === maxTentativas) throw erro;
    }
  }
  throw ultimoErro;
}

async function processarDemanda(demanda) {
  const correlationId = crypto.randomUUID();
  const inicio = Date.now();
  try {
    validarDemanda(demanda);
    const autenticacao = await chamar(`${configuracao.apiBaseUrl}/oauth/token`, {
      method: 'POST', headers: {'content-type': 'application/json', 'x-correlation-id': correlationId},
      body: JSON.stringify({client_id: configuracao.clientId, client_secret: configuracao.clientSecret})
    }, configuracao.maxTentativas);

    if (autenticacao.status !== 200 || !autenticacao.corpo.access_token) {
      return evidenciar('AUTENTICAÇÃO_RECUSADA', demanda, correlationId, inicio, autenticacao.status);
    }

    const chaveIdempotencia = crypto.createHash('sha256').update(`${demanda.demanda_id}|${demanda.data_referencia}`).digest('hex');
    const criacao = await chamar(`${configuracao.apiBaseUrl}/v1/dossies`, {
      method: 'POST', headers: {'content-type': 'application/json', authorization: `Bearer ${autenticacao.corpo.access_token}`,
        'x-correlation-id': correlationId, 'idempotency-key': chaveIdempotencia}, body: JSON.stringify(demanda)
    }, configuracao.maxTentativas);

    if (criacao.status === 201 && typeof criacao.corpo.dossie_id === 'string') {
      return evidenciar('DOSSIÊ_CRIADO', demanda, correlationId, inicio, criacao.status, criacao.corpo.dossie_id);
    }
    return evidenciar(criacao.status >= 400 && criacao.status < 500 ? 'CRIAÇÃO_RECUSADA' : 'RESPOSTA_INVÁLIDA', demanda, correlationId, inicio, criacao.status);
  } catch (erro) {
    return {...evidenciar('FALHA_TÉCNICA', demanda, correlationId, inicio), codigo_erro: String(erro.message).slice(0, 120)};
  }
}

function evidenciar(situacao, demanda, correlationId, inicio, statusHttp = null, dossieId = null) {
  return {instante: new Date().toISOString(), correlation_id: correlationId, demanda_id: demanda.demanda_id || null,
    situacao, status_http: statusHttp, dossie_id: dossieId, duracao_ms: Date.now() - inicio};
}

async function executar(arquivoEntrada) {
  const demandas = JSON.parse(fs.readFileSync(arquivoEntrada, 'utf8'));
  if (!Array.isArray(demandas)) throw new Error('ENTRADA_DEVE_SER_LISTA');
  const evidencias = [];
  for (const demanda of demandas) evidencias.push(await processarDemanda(demanda));
  const diretorio = path.resolve(__dirname, '..', 'saida');
  fs.mkdirSync(diretorio, {recursive: true});
  fs.writeFileSync(path.join(diretorio, 'evidencias.jsonl'), evidencias.map(JSON.stringify).join('\n') + '\n');
  for (const evidencia of evidencias) process.stdout.write(JSON.stringify(evidencia) + '\n');
  return evidencias;
}

if (require.main === module) executar(process.argv[2] || path.resolve(__dirname, '..', 'exemplos', 'demandas.json')).catch(erro => { console.error(erro.message); process.exitCode = 1; });
module.exports = {executar, processarDemanda};

