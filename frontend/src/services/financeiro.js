import { api } from './api'

export async function carregarCdiAtual() {
  try {
    const resposta = await api.get('/v1/financeiro/cdi/latest')
    return { modoOffline: false, cdi: resposta.data?.data ?? null, mensagem: '' }
  } catch (erro) {
    if (erro?.response?.status === 404) {
      return {
        modoOffline: false,
        cdi: null,
        mensagem: 'Taxa CDI ainda não foi carregada no cache interno. Solicite um refresh a um administrador.',
      }
    }
    console.warn('Falha ao carregar /v1/financeiro/cdi/latest; modo offline ativado.', erro)
    return {
      modoOffline: true,
      cdi: null,
      mensagem: 'API /v1/financeiro indisponível. A taxa CDI não será exibida até a conexão ser restabelecida.',
    }
  }
}

export async function atualizarCdi() {
  const resposta = await api.post('/v1/financeiro/cdi/refresh')
  return resposta.data
}

export function formatarPercentual(valor, casas = 6) {
  if (typeof valor !== 'number') return '-'
  return `${valor.toFixed(casas)}%`
}
