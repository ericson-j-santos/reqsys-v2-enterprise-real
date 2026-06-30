import { computed, onMounted, ref } from 'vue'
import { api } from '../services/api'
import { FRONTEND_VERSION } from '../constants/appVersion'

export function useAppVersion({ fetchOnMount = true } = {}) {
  const apiVersion = ref(null)
  const apiEnvironment = ref(null)
  const loading = ref(false)
  const error = ref(false)

  const versionsAligned = computed(() => {
    if (!apiVersion.value) return null
    return apiVersion.value === FRONTEND_VERSION
  })

  const versionLabel = computed(() => {
    if (!apiVersion.value) return `v${FRONTEND_VERSION}`
    if (versionsAligned.value) return `v${FRONTEND_VERSION}`
    return `FE v${FRONTEND_VERSION} · API v${apiVersion.value}`
  })

  async function loadRuntimeVersion() {
    loading.value = true
    error.value = false
    try {
      const { data } = await api.get('/runtime/version')
      const payload = data?.data ?? data
      apiVersion.value = payload?.version ?? null
      apiEnvironment.value = payload?.environment ?? null
    } catch {
      error.value = true
    } finally {
      loading.value = false
    }
  }

  if (fetchOnMount) {
    onMounted(loadRuntimeVersion)
  }

  return {
    frontendVersion: FRONTEND_VERSION,
    apiVersion,
    apiEnvironment,
    versionsAligned,
    versionLabel,
    loading,
    error,
    loadRuntimeVersion,
  }
}
