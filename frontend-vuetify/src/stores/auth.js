import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'
import { loginMicrosoft as iniciarLoginMicrosoft } from '../services/microsoftAuth'

function fixUtf8(str) {
  if (!str) return str
  try {
    return decodeURIComponent(escape(str))
  } catch {
    return str
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('reqsys_token') || null)
  const usuario = ref(null)

  const autenticado = computed(() => !!token.value)

  async function login(email, senha) {
    const { data } = await api.post('/v1/auth/login', { email, senha })
    aplicarSessao(data)
  }

  async function loginMicrosoft() {
    const data = await iniciarLoginMicrosoft()
    aplicarSessao(data)
  }

  function sair() {
    token.value = null
    usuario.value = null
    localStorage.removeItem('reqsys_token')
  }

  function pode(recurso) {
    if (!usuario.value?.permissoes) return false
    return usuario.value.permissoes.includes(recurso)
  }

  function aplicarSessao(response) {
    const data = response?.data ?? response
    token.value = data.access_token ?? data.token
    localStorage.setItem('reqsys_token', token.value)
    const user = data.usuario ?? data.user ?? {}
    usuario.value = {
      ...user,
      nome: fixUtf8(user.nome),
      email: fixUtf8(user.email),
      papel: fixUtf8(user.papel),
    }
  }

  return { token, usuario, autenticado, login, loginMicrosoft, sair, pode }
})
