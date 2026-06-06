<template>
  <main class="login-page">
    <v-card class="login-card" :width="cardWidth">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
        <span>ReqSys Enterprise</span>
        <v-tooltip text="Ambiente de acesso corporativo com perfil e permissões" location="top">
          <template #activator="{ props }">
            <v-chip v-bind="props" size="small" color="amber" variant="tonal">RBAC</v-chip>
          </template>
        </v-tooltip>
      </v-card-title>
      <v-card-subtitle>Login corporativo com RBAC</v-card-subtitle>

      <v-card-text>
        <!-- Botão Microsoft (principal) -->
        <v-btn
          v-if="azureDisponivel !== false"
          block
          size="large"
          variant="outlined"
          class="mb-4 btn-microsoft"
          :loading="carregandoAzure"
          :disabled="carregandoDemo"
          prepend-icon="mdi-microsoft"
          @click="entrarMicrosoft"
        >
          Entrar com conta Microsoft
        </v-btn>

        <v-divider v-if="azureDisponivel !== false" class="mb-4">
          <span class="text-caption text-medium-emphasis px-2">ou</span>
        </v-divider>

        <!-- Login demo (desenvolvimento) -->
        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
          Acesso demo — apenas para desenvolvimento
        </v-alert>

        <v-text-field
          v-model="email"
          label="E-mail"
          variant="outlined"
          prepend-inner-icon="mdi-email-outline"
          class="mb-2"
          :disabled="carregandoDemo || carregandoAzure"
        />

        <v-text-field
          v-model="senha"
          label="Senha"
          :type="mostrarSenha ? 'text' : 'password'"
          variant="outlined"
          prepend-inner-icon="mdi-lock-outline"
          :append-inner-icon="mostrarSenha ? 'mdi-eye-off' : 'mdi-eye'"
          :disabled="carregandoDemo || carregandoAzure"
          @click:append-inner="mostrarSenha = !mostrarSenha"
        />

        <v-alert v-if="erro" type="error" density="compact" class="mt-1">{{ erro }}</v-alert>
      </v-card-text>

      <v-card-actions class="px-4 pb-4 flex-column ga-2">
        <v-btn
          block
          color="amber"
          size="large"
          :loading="carregandoDemo"
          :disabled="carregandoAzure"
          @click="entrarDemo"
        >
          Entrar (demo)
        </v-btn>
      </v-card-actions>
    </v-card>
  </main>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { useAuthStore } from '../stores/auth'
import { getMsalInstance, loginMicrosoft, handleRedirectResult } from '../auth/msal'
import { api } from '../services/api'

const { width } = useDisplay()
const cardWidth = computed(() => Math.min(440, width.value - 32))

const email = ref('ericsonjosedossantos@tieri659.onmicrosoft.com')
const senha = ref('admin123')
const erro = ref('')
const carregandoDemo = ref(false)
const carregandoAzure = ref(false)
const mostrarSenha = ref(false)
const azureDisponivel = ref(null)
const auth = useAuthStore()
const router = useRouter()

onMounted(async () => {
  // Verificar se Azure está configurado
  try {
    const { data } = await api.get('/v1/auth/config')
    azureDisponivel.value = data.data.azure_enabled
  } catch {
    azureDisponivel.value = false
  }

  // Processar redirect de volta do Microsoft
  try {
    const idToken = await handleRedirectResult()
    if (idToken) await _autenticarComToken(idToken)
  } catch (e) {
    erro.value = `Erro no retorno Microsoft: ${e.message}`
  }
})

async function entrarMicrosoft() {
  carregandoAzure.value = true
  erro.value = ''
  try {
    const idToken = await loginMicrosoft()
    if (idToken) await _autenticarComToken(idToken)
  } catch (e) {
    const code = e.errorCode ?? ''
    if (code === 'user_cancelled' || e.message?.includes('user_cancelled')) {
      erro.value = ''  // cancelamento não é erro
    } else if (code === 'popup_window_error' || code === 'empty_window_error') {
      erro.value = 'Popup bloqueado pelo navegador. Permita popups para este site e tente novamente.'
    } else {
      erro.value = `Erro Microsoft: ${e.message ?? code ?? e}`
    }
  } finally {
    carregandoAzure.value = false
  }
}

async function _autenticarComToken(idToken) {
  const { data } = await api.post('/v1/auth/azure', { id_token: idToken })
  auth.salvarSessao(data.data)
  router.push('/')
}

async function entrarDemo() {
  carregandoDemo.value = true
  erro.value = ''
  try {
    await auth.login({ email: email.value, senha: senha.value })
    router.push('/')
  } catch {
    erro.value = 'Falha no login demo'
  } finally {
    carregandoDemo.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: var(--bg);
}
.login-card {
  width: 100%;
}
.btn-microsoft {
  border-color: #0078d4 !important;
  color: #0078d4 !important;
}
</style>
