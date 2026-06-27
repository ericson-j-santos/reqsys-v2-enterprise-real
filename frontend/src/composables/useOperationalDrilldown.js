import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  criarQueryFiltrosMonitoramento,
  normalizarFiltrosMonitoramento,
  possuiFiltroMonitoramentoAtivo,
} from '../utils/filtrosMonitoramento'

const ROTULOS_FILTRO = {
  estado: 'Estado',
  secao: 'Seção',
  severidade: 'Severidade',
  correlation_id: 'Correlation',
  busca: 'Busca',
}

export function useOperationalDrilldown(opcoes = {}) {
  const route = useRoute()
  const router = useRouter()
  const rotaBase = opcoes.rotaBase || route.path

  const filtros = computed(() => normalizarFiltrosMonitoramento(route.query))

  const filtrosAtivos = computed(() => Object.entries(filtros.value)
    .filter(([, valor]) => Boolean(String(valor ?? '').trim()))
    .map(([chave, valor]) => ({
      key: chave,
      label: ROTULOS_FILTRO[chave] || chave,
      value: valor,
    })))

  const possuiFiltros = computed(() => possuiFiltroMonitoramentoAtivo(route.query))

  const breadcrumbs = computed(() => {
    const trilha = [{ label: 'Analytics', path: '/analytics' }]
    if (route.path === '/monitoramento-operacional') {
      trilha.push({ label: 'Monitoramento', path: '/monitoramento-operacional' })
    } else if (route.path === '/estatisticas') {
      trilha.push({ label: 'Estatísticas', path: '/estatisticas' })
    } else if (route.path === '/analytics') {
      return [{ label: 'Analytics Navegável', path: '/analytics' }]
    }
    if (filtros.value.secao) {
      trilha.push({ label: `Seção: ${filtros.value.secao}`, path: route.path })
    }
    return trilha
  })

  function aplicarFiltros(novosFiltros = {}) {
    const query = criarQueryFiltrosMonitoramento({
      ...filtros.value,
      ...novosFiltros,
    })
    router.push({ path: rotaBase, query })
  }

  function removerFiltro(chave) {
    const query = { ...route.query }
    delete query[chave]
    router.replace({ path: rotaBase, query })
  }

  function limparFiltros() {
    router.replace({ path: rotaBase, query: {} })
  }

  function irPara(rota) {
    if (!rota?.path) return
    router.push(rota)
  }

  return {
    filtros,
    filtrosAtivos,
    possuiFiltros,
    breadcrumbs,
    aplicarFiltros,
    removerFiltro,
    limparFiltros,
    irPara,
  }
}
