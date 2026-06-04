import { defineStore } from 'pinia'
import { api } from '../services/api'

function fixMojibake(value) {
  if (typeof value !== 'string' || !/[ÃÂ]/.test(value)) return value
  try {
    const bytes = Uint8Array.from(value, (char) => char.charCodeAt(0))
    return new TextDecoder('utf-8').decode(bytes)
  } catch {
    return value
  }
}

function sanitizeUsuario(usuario) {
  if (!usuario || typeof usuario !== 'object') return usuario
  return {
    ...usuario,
    nome: fixMojibake(usuario.nome),
    email: fixMojibake(usuario.email),
    papel: fixMojibake(usuario.papel),
  }
}

function loadUsuario() {
  try {
    const raw = localStorage.getItem('reqsys_usuario')
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({ usuario: loadUsuario(), token: localStorage.getItem('reqsys_token') || null }),
  getters: {
    autenticado: (s) => Boolean(s.token),
    permissoes: (s) => s.usuario?.permissoes || [],
  },
  actions: {
    async login(credenciais) {
      const { data } = await api.post('/v1/auth/login', credenciais)
      this.token = data.data.access_token
      this.usuario = sanitizeUsuario(data.data.usuario)
      localStorage.setItem('reqsys_token', this.token)
      localStorage.setItem('reqsys_usuario', JSON.stringify(this.usuario))
    },
    sair() {
      this.token = null
      this.usuario = null
      localStorage.removeItem('reqsys_token')
      localStorage.removeItem('reqsys_usuario')
    },
    pode(recurso) { return this.permissoes.includes(recurso) }
  }
})
