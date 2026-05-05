import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

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
    token.value = data.access_token
    localStorage.setItem('reqsys_token', token.value)
    usuario.value = {
      ...data.usuario,
      nome: fixUtf8(data.usuario.nome),
      email: fixUtf8(data.usuario.email),
      papel: fixUtf8(data.usuario.papel),
    }
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

  return { token, usuario, autenticado, login, sair, pode }
})
