import { describe, expect, it } from 'vitest'

import {
  POLITICAS_TEAMS_CANONICAS,
  detalheErroPolitica,
  mascararDestino,
} from '../teamsRecipientPolicies'

describe('teamsRecipientPolicies', () => {
  it('mantem somente as duas politicas canonicas da governanca atual', () => {
    expect(POLITICAS_TEAMS_CANONICAS.map((item) => item.id)).toEqual([
      'hitl-approvers',
      'reqsys-operations',
    ])
  })

  it('mascara endereco sem ocultar o dominio necessario para reconhecimento operacional', () => {
    const mascarado = mascararDestino('aprovador@example.com')
    expect(mascarado).toContain('@example.com')
    expect(mascarado).not.toContain('aprovador@example.com')
    expect(mascarado.startsWith('ap')).toBe(true)
  })

  it('mascara identificador opaco', () => {
    const valor = 'abc123456789xyz'
    const mascarado = mascararDestino(valor)
    expect(mascarado).not.toBe(valor)
    expect(mascarado.startsWith('abc')).toBe(true)
    expect(mascarado.endsWith('yz')).toBe(true)
  })

  it('traduz recusas de autorizacao sem expor detalhes internos', () => {
    expect(detalheErroPolitica({ response: { status: 401 } })).toContain('sessão')
    expect(detalheErroPolitica({ response: { status: 403 } })).toContain('administradores')
  })

  it('preserva mensagem de conflito conhecida', () => {
    expect(detalheErroPolitica({
      response: { status: 409, data: { detail: 'Destinatario ja cadastrado nesta politica.' } },
    })).toBe('Destinatario ja cadastrado nesta politica.')
  })
})
