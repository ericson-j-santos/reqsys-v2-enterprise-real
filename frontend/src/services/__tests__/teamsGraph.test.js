import { describe, expect, it, vi } from 'vitest'
import { enviarMensagemChatTeams, listarChatsTeams, rotuloChat } from '../teamsGraph'
import { api } from '../api'
import { acquireTeamsGraphToken, getContaAtual } from '../../auth/msal'

vi.mock('../api', () => ({
  api: {
    post: vi.fn(),
  },
}))

vi.mock('../../auth/msal', () => ({
  acquireTeamsGraphToken: vi.fn(),
  getContaAtual: vi.fn(),
}))

describe('enviarMensagemChatTeams', () => {
  it('adquire o token delegado e envia ao endpoint chat-delegado', async () => {
    acquireTeamsGraphToken.mockResolvedValue('delegated-token')
    api.post.mockResolvedValue({ data: { data: { enviado: true, message_id: 'msg-1', chat_id: 'chat-1' } } })

    const resultado = await enviarMensagemChatTeams('chat-1', 'Ola time')

    expect(acquireTeamsGraphToken).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/v1/hub-lowcode/teams/graph/mensagens/chat-delegado', {
      chat_id: 'chat-1',
      texto: 'Ola time',
      content_type: 'text',
      usuario_access_token: 'delegated-token',
    })
    expect(resultado).toEqual({ enviado: true, message_id: 'msg-1', chat_id: 'chat-1' })
  })

  it('propaga erro quando a aquisicao do token falha (ex.: usuario nao logado)', async () => {
    acquireTeamsGraphToken.mockRejectedValue(new Error('Nenhuma conta Microsoft logada'))

    await expect(enviarMensagemChatTeams('chat-1', 'Ola')).rejects.toThrow('Nenhuma conta Microsoft logada')
    expect(api.post).not.toHaveBeenCalled()
  })
})

describe('rotuloChat', () => {
  it('usa o topico quando presente (chat de grupo nomeado)', () => {
    const chat = { id: 'chat-2', topico: 'Squad ReqSys', membros: [] }
    expect(rotuloChat(chat, 'user-eu')).toBe('Squad ReqSys')
  })

  it('usa o nome dos outros membros quando nao ha topico (chat 1:1)', () => {
    const chat = {
      id: 'chat-1',
      topico: null,
      membros: [
        { user_id: 'user-eu', nome: 'Ericson', email: 'ericson@tieri659.onmicrosoft.com' },
        { user_id: 'user-outro', nome: 'Outro Usuario', email: 'outro@tieri659.onmicrosoft.com' },
      ],
    }
    expect(rotuloChat(chat, 'user-eu')).toBe('Outro Usuario')
  })

  it('cai para o chat_id quando nao ha topico nem outros membros identificaveis', () => {
    const chat = { id: 'chat-3', topico: null, membros: [] }
    expect(rotuloChat(chat, 'user-eu')).toBe('chat-3')
  })
})

describe('listarChatsTeams', () => {
  it('adquire token e conta, e retorna chats prontos para o seletor', async () => {
    acquireTeamsGraphToken.mockResolvedValue('delegated-token')
    getContaAtual.mockResolvedValue({ localAccountId: 'user-eu' })
    api.post.mockResolvedValue({
      data: {
        data: {
          chats: [
            { id: 'chat-1', topico: null, tipo: 'oneOnOne', membros: [
              { user_id: 'user-eu', nome: 'Ericson', email: '' },
              { user_id: 'user-outro', nome: 'Outro Usuario', email: '' },
            ] },
            { id: 'chat-2', topico: 'Squad ReqSys', tipo: 'group', membros: [] },
          ],
        },
      },
    })

    const resultado = await listarChatsTeams()

    expect(api.post).toHaveBeenCalledWith('/v1/hub-lowcode/teams/graph/chats', {
      usuario_access_token: 'delegated-token',
      top: 50,
    })
    expect(resultado).toEqual([
      { id: 'chat-1', rotulo: 'Outro Usuario' },
      { id: 'chat-2', rotulo: 'Squad ReqSys' },
    ])
  })

  it('retorna lista vazia quando o backend nao retorna chats', async () => {
    acquireTeamsGraphToken.mockResolvedValue('delegated-token')
    getContaAtual.mockResolvedValue(null)
    api.post.mockResolvedValue({ data: { data: { chats: [] } } })

    expect(await listarChatsTeams()).toEqual([])
  })
})
