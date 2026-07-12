const DEFAULT_CALLBACK_PATH = '/auth/callback.html'
const DEFAULT_LOGIN_PATH = '/login'

function readEnv(name) {
  return String(import.meta.env?.[name] || '').trim()
}

function normalizeOrigin(origin) {
  return String(origin || '').trim().replace(/\/+$/, '')
}

function normalizePath(path, fallback) {
  const value = String(path || fallback).trim()
  return value.startsWith('/') ? value : `/${value}`
}

function resolveAbsoluteHttpUrl(value) {
  const raw = String(value || '').trim()
  if (!raw) return null

  try {
    const url = new URL(raw)
    if (!['http:', 'https:'].includes(url.protocol)) return null
    return url.toString()
  } catch {
    return null
  }
}

function publicOrigin() {
  return normalizeOrigin(readEnv('VITE_MSAL_PUBLIC_ORIGIN') || readEnv('VITE_PUBLIC_URL') || window.location.origin)
}

function absoluteFromEnvOrOrigin(envName, pathEnvName, fallbackPath) {
  const absoluteUri = resolveAbsoluteHttpUrl(readEnv(envName))
  if (absoluteUri) return absoluteUri

  const path = normalizePath(readEnv(pathEnvName), fallbackPath)
  return `${publicOrigin()}${path}`
}

export function getAuthCallbackUri() {
  return absoluteFromEnvOrOrigin(
    'VITE_MSAL_REDIRECT_URI',
    'VITE_MSAL_CALLBACK_PATH',
    DEFAULT_CALLBACK_PATH
  )
}

export function getPostLogoutRedirectUri() {
  return absoluteFromEnvOrOrigin(
    'VITE_MSAL_POST_LOGOUT_REDIRECT_URI',
    'VITE_MSAL_POST_LOGOUT_PATH',
    DEFAULT_LOGIN_PATH
  )
}

export function getLoginRedirectStartPageUri() {
  return absoluteFromEnvOrOrigin(
    'VITE_MSAL_LOGIN_REDIRECT_START_PAGE',
    'VITE_MSAL_LOGIN_REDIRECT_START_PATH',
    DEFAULT_LOGIN_PATH
  )
}
