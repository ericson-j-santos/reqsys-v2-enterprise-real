import { computed, onMounted, ref } from 'vue'
import { api } from '../services/api'
import { FRONTEND_VERSION } from '../constants/appVersion'

function shortenSha(sha) {
  if (!sha || sha === 'unknown') return null
  return sha.length > 7 ? sha.slice(0, 7) : sha
}

function applyRuntimePayload(payload, refs) {
  refs.apiVersion.value = payload?.version ?? null
  refs.apiEnvironment.value = payload?.environment ?? null
  refs.apiBuildSha.value = payload?.build_sha ?? null
}

export function useAppVersion({ fetchOnMount = true } = {}) {
  const apiVersion = ref(null)
  const apiEnvironment = ref(null)
  const apiBuildSha = ref(null)
  const loading = ref(false)
  const error = ref(false)

  const refs = { apiVersion, apiEnvironment, apiBuildSha }

  const versionsAligned = computed(() => {
    if (!apiVersion.value) return null
    return apiVersion.value === FRONTEND_VERSION
  })

  const hasVersionDrift = computed(() => versionsAligned.value === false)

  const apiBuildShaShort = computed(() => shortenSha(apiBuildSha.value))

  const versionLabel = computed(() => {
    if (!apiVersion.value) return `v${FRONTEND_VERSION}`
    if (versionsAligned.value) return `v${FRONTEND_VERSION}`
    return `FE v${FRONTEND_VERSION} · API v${apiVersion.value}`
  })

  async function loadFromBuildInfo() {
    const { data } = await api.get('/runtime/build-info')
    applyRuntimePayload(data?.data ?? data, refs)
  }

  async function loadFromVersion() {
    const { data } = await api.get('/runtime/version')
    applyRuntimePayload(data?.data ?? data, refs)
  }

  async function loadRuntimeVersion() {
    loading.value = true
    error.value = false
    try {
      await loadFromBuildInfo()
    } catch {
      try {
        await loadFromVersion()
      } catch {
        error.value = true
      }
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
    apiBuildSha,
    apiBuildShaShort,
    versionsAligned,
    hasVersionDrift,
    versionLabel,
    loading,
    error,
    loadRuntimeVersion,
  }
}
