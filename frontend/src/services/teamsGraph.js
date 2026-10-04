import { api } from './api'
import { acquireTeamsGraphToken, getContaAtual } from '../auth/msal'

export async function enviarMensagemChatTeams(chatId, texto, contentType = 'text') {
  const usuarioAccessToken = await acquireTeamsGraphToken()
  const { data } = await api.post('/v1/hub-lowcode/teams/graph/mensagens/chat-delegado', {
    chat_id: chatId,
    texto,
    content_type: contentType,
    usuario_access_token: usuarioAccessToken,
  })
  return data.data
}

export function rotuloChat(chat, meuUserId) {
  if (chat.topico) return chat.topico
  const outros = (chat.membros || [])
    .filter((m) => m.user_id !== meuUserId)
    .map((m) => m.nome || m.email)
    .filter(Boolean)
  return outros.length ? outros.join(', ') : chat.id
}

// Lista os chats (1:1/grupo) do usuário logado, prontos para um seletor
// (item-title="rotulo", item-value="id") — evita ter que descobrir/colar o
// chat_id manualmente.
export async function listarChatsTeams(top = 50) {
  const [usuarioAccessToken, conta] = await Promise.all([acquireTeamsGraphToken(), getContaAtual()])
  const { data } = await api.post('/v1/hub-lowcode/teams/graph/chats', {
    usuario_access_token: usuarioAccessToken,
    top,
  })
  const chats = data.data?.chats || []
  return chats.map((chat) => ({ id: chat.id, rotulo: rotuloChat(chat, conta?.localAccountId) }))
}
