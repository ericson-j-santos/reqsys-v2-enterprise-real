import { ref } from 'vue'

/**
 * Composable institucional para gerenciar estados de loading/error/warning
 * em views Vuetify — espelha o InstitucionalStatusBannerComponent Angular.
 *
 * Uso:
 *   const { loading, errorMessage, warningMessage, setLoading, setError, setWarning, clearAll } = useStatusBanner()
 */
export function useStatusBanner () {
  const loading        = ref(false)
  const errorMessage   = ref('')
  const warningMessage = ref('')

  function setLoading (value = true) {
    loading.value        = value
    if (value) {
      errorMessage.value   = ''
      warningMessage.value = ''
    }
  }

  function setError (msg) {
    loading.value        = false
    errorMessage.value   = msg || 'Ocorreu um erro inesperado.'
    warningMessage.value = ''
  }

  function setWarning (msg) {
    loading.value        = false
    warningMessage.value = msg || ''
    errorMessage.value   = ''
  }

  function clearAll () {
    loading.value        = false
    errorMessage.value   = ''
    warningMessage.value = ''
  }

  return { loading, errorMessage, warningMessage, setLoading, setError, setWarning, clearAll }
}
