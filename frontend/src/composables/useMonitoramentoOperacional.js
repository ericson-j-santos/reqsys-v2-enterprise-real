import { ref } from 'vue'
import { calcularResumoSemaforo } from '../utils/filtrosMonitoramento'

export function useMonitoramentoOperacional() {
  const resumo = ref({})
  const itens = ref([])
  const modoColeta = ref('')
  const coletaDetalhes = ref({})
  const carregando = ref(false)
  const erro = ref('')

  async function carregarMonitoramento() {
    const resposta = await fetch('/api/monitoramento-operacional', { headers: { Accept: 'application/json' } })
    if (!resposta.ok) throw new Error('Falha ao carregar monitoramento operacional')
    const payload = await resposta.json()
    resumo.value = payload.data?.resumo || {}
    itens.value = payload.data?.itens || []
    modoColeta.value = payload.data?.modo_coleta || ''
    coletaDetalhes.value = payload.data?.coleta_detalhes || {}
    return payload.data
  }

  function resumoSemaforo() {
    return calcularResumoSemaforo(itens.value)
  }

  return {
    resumo,
    itens,
    modoColeta,
    coletaDetalhes,
    carregando,
    erro,
    carregarMonitoramento,
    resumoSemaforo,
  }
}
