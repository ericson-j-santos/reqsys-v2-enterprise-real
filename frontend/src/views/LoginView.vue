<template>
  <main class="login-page" data-testid="route-login">
    <v-card class="login-card" :width="cardWidth" elevation="0">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2 login-card-title">
        <span class="login-brand"><span class="brand-dot">R</span> ReqSys Enterprise</span>
        <span class="figma-pill figma-pill--compact">RBAC</span>
      </v-card-title>
      <v-card-subtitle class="login-card-subtitle">Login corporativo - Tieri659</v-card-subtitle>

      <v-card-text>
        <v-btn
          v-if="azureDisponivel"
          block
          size="large"
          variant="outlined"
          class="mb-4 btn-microsoft"
          :loading="carregandoAzure"
          prepend-icon="mdi-microsoft"
          @click="entrarMicrosoft"
        >
          Entrar com conta Microsoft
        </v-btn>

        <v-alert
          v-if="!azureDisponivel && !demoLoginDisponivel"
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-4"
        >
          <div class="font-weight-medium">Autenticacao corporativa indisponivel.</div>
          <div>{{ mensagemDiagnosticoAuth }}</div>
          <div v-if="camposAusentes.length" class="mt-2 text-caption">
            Campos ausentes: {{ camposAusentes.join(', ') }}
          </div>
          <div v-if="redirectEsperado" class="mt-1 text-caption">
            Redirect URI esperado no Microsoft Entra ID: {{ redirectEsperado }}
          </div>
        </v-alert>

        <template v-if="demoLoginDisponivel">
          <v-divider v-if="azureDisponivel" class="mb-4">
            <span class="text-caption text-medium-emphasis px-2">ou</span>
          </v-divider>

          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            Acesso demo - apenas para desenvolvimento
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
        </template>

        <v-alert
          v-if="erro"
          type="error"
          color="#b91c1c"
          density="compact"
          class="mt-1 login-error-alert"
        >
          {{ erro }}
        </v-alert>
      </v-card-text>

      <v-card-actions v-if="demoLoginDisponivel" class="px-4 pb-4">
        <v-btn
          block
          color="primary"
          size="large"
          class="figma-btn-entrar"
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
import { useRoute, useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { useAuthStore } from '../stores/auth'
import { loginMicrosoftRedirect } from '../auth/msal'
import { api } from '../services/api'

const { width } = useDisplay()
const cardWidth = computed(() => Math.min(440, width.value - 32))

const email = ref('ericsonjosedossantos@tieri659.onmicrosoft.com')
const senha = ref('')
const erro = ref('')
const carregandoDemo = ref(false)
const carregandoAzure = ref(false)
const mostrarSenha = ref(false)
const azureDisponivel = ref(false)
const demoLoginDisponivel = ref(false)
const azureConfig = ref(null)

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const camposAusentes = computed(() => azureConfig.value?.missing_fields || [])
const redirectEsperado = computed(() => azureConfig.value?.expected_redirect_uri || '')
const mensagemDiagnosticoAuth = computed(() => {
  return azureConfig.value?.operator_action || 'Verifique a configuracao do Azure AD no backend.'
})

onMounted(async () => {
  const azureErr = sessionStorage.getItem('azure_login_error')
  if (azureErr) {
    erro.value = azureErr
    sessionStorage.removeItem('azure_login_error')
  }

  try {
    const { data } = await api.get('/v1/auth/config')
    azureConfig.value = data.data
    azureDisponivel.value = Boolean(data.data.azure_enabled)
    demoLoginDisponivel.value = Boolean(data.data.demo_login_enabled)
  } catch {
    erro.value = 'Nao foi possivel obter a configuracao de autenticacao do servidor.'
  }
})

async function entrarMicrosoft() {
  if (!azureConfig.value) return
  carregandoAzure.value = true
  erro.value = ''
  try {
    await loginMicrosoftRedirect()
  } catch (e) {
    erro.value = e.response?.data?.detail || e.message || 'Falha no login Microsoft'
    carregandoAzure.value = false
  }
}

async function entrarDemo() {
  carregandoDemo.value = true
  erro.value = ''
  try {
    await auth.login({ email: email.value, senha: senha.value })
    const destino = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(destino.startsWith('/login') ? '/' : destino)
  } catch (e) {
    erro.value = e.response?.data?.detail || 'Falha no login demo'
  } finally {
    carregandoDemo.value = false
  }
}
</script>

<style scoped>
.login-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 800;
}

.login-card-title,
.login-card-subtitle {
  color: var(--text) !important;
}

.figma-btn-entrar {
  border-radius: 999px !important;
  font-weight: 700 !important;
}

.btn-microsoft {
  border-color: #38bdf8 !important;
  color: #38bdf8 !important;
}

.login-error-alert {
  color: #ffffff !important;
}
</style>
