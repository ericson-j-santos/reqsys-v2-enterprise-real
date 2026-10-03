export const POST_LOGIN_REDIRECT_KEY = 'reqsys_post_login_redirect_v1'

export function normalizePostLoginRedirect(value) {
  if (typeof value !== 'string') return '/'
  if (!value.startsWith('/') || value.startsWith('//') || value.startsWith('/login')) return '/'
  return value
}

export function persistPostLoginRedirect(value, storage = window.sessionStorage) {
  const destination = normalizePostLoginRedirect(value)
  storage.setItem(POST_LOGIN_REDIRECT_KEY, destination)
  return destination
}

export function consumePostLoginRedirect(storage = window.sessionStorage) {
  const destination = normalizePostLoginRedirect(storage.getItem(POST_LOGIN_REDIRECT_KEY))
  storage.removeItem(POST_LOGIN_REDIRECT_KEY)
  return destination
}
