import { NAV_ITEMS_FLAT } from '../constants/navCatalog'

export function normalizarBusca(texto) {
  return String(texto ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('pt-BR')
    .trim()
}

export function filtrarNavegacaoPermitida(itens, resolverRota, podeAcessar) {
  return itens.filter((item) => {
    const rota = resolverRota(item.to)
    if (!rota?.matched?.length || rota.name === 'not-found') return false
    return !rota.meta?.recurso || podeAcessar(rota.meta.recurso)
  })
}

export function buscarNavegacao(consulta, itens = NAV_ITEMS_FLAT, limite = 12) {
  const termos = normalizarBusca(consulta).split(/\s+/).filter(Boolean)
  if (!termos.length || limite <= 0) return []

  const unicos = new Map()
  for (const item of itens) {
    const titulo = normalizarBusca(item.title)
    const descricao = normalizarBusca(item.tip)
    const secao = normalizarBusca(item.temaTitle)
    const destino = normalizarBusca(item.to)
    const texto = [titulo, descricao, secao, destino].join(' ')
    if (!termos.every((termo) => texto.includes(termo))) continue

    const pontuacao = termos.reduce((soma, termo) => soma
      + (titulo === termo ? 12 : titulo.startsWith(termo) ? 8 : titulo.includes(termo) ? 5 : 0)
      + (descricao.includes(termo) ? 2 : 0)
      + (secao.includes(termo) ? 1 : 0), 0)
    const anterior = unicos.get(item.to)
    if (!anterior || pontuacao > anterior.pontuacao) unicos.set(item.to, { ...item, pontuacao })
  }

  return [...unicos.values()]
    .sort((a, b) => b.pontuacao - a.pontuacao || a.title.localeCompare(b.title, 'pt-BR'))
    .slice(0, limite)
}
