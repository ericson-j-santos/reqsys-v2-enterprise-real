const http = require('node:http');
const crypto = require('node:crypto');

function responder(res, status, corpo) {
  res.writeHead(status, {'content-type': 'application/json; charset=utf-8'});
  res.end(JSON.stringify(corpo));
}

async function lerJson(req) {
  const partes = [];
  for await (const parte of req) partes.push(parte);
  return JSON.parse(Buffer.concat(partes).toString('utf8') || '{}');
}

const servidor = http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/saude') return responder(res, 200, {status: 'saudavel'});

    if (req.method === 'POST' && req.url === '/oauth/token') {
      const corpo = await lerJson(req);
      if (corpo.client_id !== 'cliente-treinamento' || !corpo.client_secret) {
        return responder(res, 401, {codigo: 'CREDENCIAL_INVALIDA'});
      }
      return responder(res, 200, {access_token: 'mock-token-sintetico', token_type: 'Bearer', expires_in: 300});
    }

    if (req.method === 'POST' && req.url === '/v1/dossies') {
      const corpo = await lerJson(req);
      if (req.headers.authorization !== 'Bearer mock-token-sintetico') return responder(res, 401, {codigo: 'NAO_AUTORIZADO'});
      if (!req.headers['x-correlation-id'] || !req.headers['idempotency-key']) return responder(res, 400, {codigo: 'CABECALHO_OBRIGATORIO'});
      if (corpo.simular_falha) return responder(res, 422, {codigo: 'REGRA_NEGOCIO_RECUSADA'});
      const sufixo = crypto.createHash('sha256').update(corpo.demanda_id).digest('hex').slice(0, 12).toUpperCase();
      return responder(res, 201, {dossie_id: `DOS-${sufixo}`, situacao: 'CRIADO'});
    }

    responder(res, 404, {codigo: 'RECURSO_NAO_ENCONTRADO'});
  } catch {
    responder(res, 400, {codigo: 'JSON_INVALIDO'});
  }
});

servidor.listen(Number(process.env.PORT || 8080), '127.0.0.1', () => {
  process.stdout.write(JSON.stringify({evento: 'SERVIDOR_INICIADO', porta: Number(process.env.PORT || 8080)}) + '\n');
});

