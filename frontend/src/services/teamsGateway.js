import { api } from './api'
import { acquireTeamsGraphToken } from '../auth/msal'

export async function obterStatusTeamsGateway() {
  const { data } = await api.get('/v1/teams-gateway/status')
  return data.data
}

export async function simularRotaTeamsGateway(payload) {
  const { data } = await api.post('/v1/teams-gateway/routes', payload)
  return data.data
}

export async function enviarMensagemTeamsGateway(payload) {
  const { data } = await api.post('/v1/teams-gateway/messages', payload)
  return data.data
}

export async function enviarChatDelegadoTeamsGateway({ chatId, texto, contentType = 'text', autor = 'reqsys', metadata = {} }) {
  const usuarioAccessToken = await acquireTeamsGraphToken()
  return enviarMensagemTeamsGateway({
    destino_tipo: 'chat',
    modo: 'graph_delegado',
    destino_id: chatId,
    texto,
    content_type: contentType,
    usuario_access_token: usuarioAccessToken,
    autor,
    metadata,
  })
}

export async function enviarWebhookTeamsGateway({ texto, webhookUrl, autor = 'reqsys', metadata = {} }) {
  const { data } = await api.post('/v1/teams-gateway/messages/webhook', {
    destino_tipo: 'canal',
    texto,
    webhook_url: webhookUrl,
    autor,
    metadata,
  })
  return data.data
}
