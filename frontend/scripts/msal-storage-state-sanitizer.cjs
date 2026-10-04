const EPHEMERAL_REQSYS_KEYS = new Set(['reqsys_token', 'reqsys_usuario'])

function sanitizeStorageState(storageState, appOrigin) {
  const state = JSON.parse(JSON.stringify(storageState || { cookies: [], origins: [] }))
  state.origins = Array.isArray(state.origins) ? state.origins.map((entry) => {
    if (!entry || (appOrigin && entry.origin !== appOrigin)) return entry
    return {
      ...entry,
      localStorage: Array.isArray(entry.localStorage)
        ? entry.localStorage.filter((item) => !EPHEMERAL_REQSYS_KEYS.has(item?.name))
        : [],
    }
  }) : []
  return state
}

module.exports = { sanitizeStorageState }
