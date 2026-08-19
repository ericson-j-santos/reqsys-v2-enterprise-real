<template>
  <v-alert
    v-if="forbiddenResource"
    class="req-route-feedback"
    type="warning"
    variant="tonal"
    border="start"
    data-testid="route-feedback-forbidden"
  >
    <strong>Acesso bloqueado.</strong>
    Seu perfil atual não possui permissão para o recurso solicitado:
    <code>{{ forbiddenResource }}</code>.
    Atualize as permissões da sessão ou force uma nova autenticação.

    <div class="d-flex flex-wrap ga-2 mt-3">
      <v-btn size="small" color="primary" variant="flat" :loading="atualizando" @click="atualizarPermissoes">
        Atualizar permissões
      </v-btn>
      <v-btn size="small" color="warning" variant="outlined" @click="resetarSessao">
        Resetar sessão e autenticar novamente
      </v-btn>
    </div>

    <div v-if="erroSessao" class="text-caption mt-2" role="status">
      {{ erroSessao }}
    </div>
  </v-alert>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const atualizando = ref(false)
const erroSessao = ref('')

const forbiddenResource = computed(() => {
  const value = route.query.forbidden
  return typeof value === 'string' ? value : ''
})

const forbiddenPath = computed(() => {
  const value = route.query.forbidden_path
  return typeof value === 'string' && value.startsWith('/') ? value : '/'
})

async function atualizarPermissoes() {
  atualizando.value = true
  erroSessao.value = ''
  try {
    await auth.atualizarSessao()
    if (auth.pode(forbiddenResource.value)) {
      await router.replace(forbiddenPath.value)
      return
    }
    erroSessao.value = 'A permissão continua indisponível após a atualização da sessão.'
  } catch (error) {
    if (error?.response?.status === 401) return
    erroSessao.value = 'Não foi possível atualizar a sessão. Tente novamente ou force uma nova autenticação.'
  } finally {
    atualizando.value = false
  }
}

function resetarSessao() {
  const destino = forbiddenPath.value
  auth.sair()
  router.replace({ path: '/login', query: { redirect: destino, reset: 'security' } })
}
</script>
