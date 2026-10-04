import { api } from '../services/api'

export async function loginWithCertificateAgent() {
  const agent = window.ReqSysCertificateAgent
  if (!agent || typeof agent.signChallenge !== 'function') {
    throw new Error('Agente de certificado digital nao encontrado neste navegador.')
  }

  const challengeResponse = await api.post('/v1/auth/certificate/challenge')
  const challenge = challengeResponse.data.data.challenge
  const signed = await agent.signChallenge({ challenge, algorithm: 'SHA256' })

  if (!signed?.certificate_pem || !signed?.signature_base64) {
    throw new Error('O agente de certificado nao retornou certificado e assinatura.')
  }

  const { data } = await api.post('/v1/auth/certificate/verify', {
    certificate_pem: signed.certificate_pem,
    challenge,
    signature_base64: signed.signature_base64,
  })
  return data.data
}
