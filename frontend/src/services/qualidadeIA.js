import { api } from './api'

function baixarBlob(blob, nomeArquivo) {
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = nomeArquivo
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
}

function buildParams(limit, dias) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (dias != null) params.set('dias', String(dias))
    return params.toString()
}

export const qualidadeIAService = {
    async baixarTendenciaCsv(limit = 200, dias = null) {
        const nome = dias ? `qualidade-ia-tendencia-${dias}d.csv` : 'qualidade-ia-tendencia.csv'
        const resp = await api.get(`/v1/qualidade-ia/tendencia.csv?${buildParams(limit, dias)}`, {
            responseType: 'blob',
        })
        baixarBlob(new Blob([resp.data], { type: 'text/csv;charset=utf-8' }), nome)
    },

    async baixarTendenciaPdf(limit = 200, dias = null) {
        const nome = dias ? `qualidade-ia-tendencia-${dias}d.pdf` : 'qualidade-ia-tendencia.pdf'
        const resp = await api.get(`/v1/qualidade-ia/tendencia.pdf?${buildParams(limit, dias)}`, {
            responseType: 'blob',
        })
        baixarBlob(new Blob([resp.data], { type: 'application/pdf' }), nome)
    },
}
