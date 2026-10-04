import { ref } from 'vue'
import {
  ambienteRequerConfirmacao,
  irParaAmbiente,
  montarUrlAmbiente,
} from '../constants/ambientesOperacionais'

export function useNavegacaoAmbiente() {
  const confirmacaoProdAberta = ref(false)
  const destinoPendente = ref(null)

  function solicitarNavegacao(ambienteId, opcoes = {}) {
    if (ambienteRequerConfirmacao(ambienteId)) {
      destinoPendente.value = {
        id: ambienteId,
        opcoes,
        url: montarUrlAmbiente(ambienteId, opcoes),
      }
      confirmacaoProdAberta.value = true
      return false
    }
    return irParaAmbiente(ambienteId, opcoes)
  }

  function confirmarNavegacaoProd() {
    if (!destinoPendente.value) return false
    const { id, opcoes } = destinoPendente.value
    confirmacaoProdAberta.value = false
    destinoPendente.value = null
    return irParaAmbiente(id, { ...opcoes, skipConfirm: true })
  }

  function cancelarNavegacaoProd() {
    confirmacaoProdAberta.value = false
    destinoPendente.value = null
  }

  return {
    confirmacaoProdAberta,
    destinoPendente,
    solicitarNavegacao,
    confirmarNavegacaoProd,
    cancelarNavegacaoProd,
  }
}
