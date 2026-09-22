import { api } from './api'

export const relatoriosService = {
  /** Lista todos os relatórios com render_url */
  listar() {
    return api.get('/v1/relatorios/ssrs')
  },

  /** Health geral do servidor SSRS */
  health() {
    return api.get('/v1/relatorios/ssrs/health')
  },

  /** Status detalhado de cada relatório (ping individual) */
  status() {
    return api.get('/v1/relatorios/ssrs/status')
  },

  /**
   * Faz download do PDF de um relatório via proxy do backend.
   * O backend lida com a autenticação Windows (NTLM/SSPI).
   */
  async downloadPdf(nome) {
    const resp = await api.get(`/v1/relatorios/ssrs/${encodeURIComponent(nome)}/pdf`, {
      responseType: 'blob',
    })
    // Cria link temporário e dispara download no navegador
    const url = URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${nome}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}
