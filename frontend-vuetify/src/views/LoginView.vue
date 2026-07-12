<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <div class="text-center mb-8">
          <v-icon size="48" color="primary" class="mb-3">mdi-layers-triple</v-icon>
          <div class="text-h4 font-weight-bold">
            <span class="text-primary">Req</span>Sys
          </div>
          <div class="text-caption text-medium-emphasis">Enterprise · Análise Ágil de Requisitos</div>
        </div>

        <v-card rounded="xl" :elevation="8">
          <v-card-text class="pa-8">
            <div class="text-h6 font-weight-medium mb-1">Acesso ao sistema</div>
            <div class="text-caption text-medium-emphasis mb-6">Use suas credenciais corporativas</div>

            <v-form @submit.prevent="efetuarLogin">
              <v-text-field
                v-model="email"
                label="E-mail"
                type="email"
                prepend-inner-icon="mdi-email-outline"
                variant="outlined"
                density="comfortable"
                :error-messages="errors.email"
                class="mb-3"
                autofocus
              />
              <v-text-field
                v-model="senha"
                label="Senha"
                :type="mostrarSenha ? 'text' : 'password'"
                prepend-inner-icon="mdi-lock-outline"
                :append-inner-icon="mostrarSenha ? 'mdi-eye-off' : 'mdi-eye'"
                variant="outlined"
                density="comfortable"
                :error-messages="errors.senha"
                class="mb-4"
                @click:append-inner="mostrarSenha = !mostrarSenha"
              />

              <v-alert v-if="errMsg" type="error" variant="tonal" class="mb-4" density="compact">
                {{ errMsg }}
              </v-alert>

              <v-btn
                type="submit"
                color="primary"
                block
                size="large"
                :loading="carregando"
              >
                <v-icon start>mdi-login</v-icon>
                Entrar
              </v-btn>
            </v-form>

            <div class="login-divider">
              <span>ou</span>
            </div>

            <v-btn
              color="primary"
              variant="outlined"
              block
              size="large"
              :loading="carregandoMicrosoft"
              @click="entrarComMicrosoft"
            >
              <v-icon start>mdi-microsoft</v-icon>
              Entrar com Microsoft
            </v-btn>
          </v-card-text>

          <v-divider />
          <v-card-text class="pa-4">
            <div class="text-caption text-medium-emphasis mb-2 font-weight-medium">Credenciais de demonstração:</div>
            <div class="d-flex flex-wrap gap-2">
              <v-chip
                v-for="demo in demos"
                :key="demo.email"
                size="small"
                variant="outlined"
                color="primary"
                class="cursor-pointer"
                @click="preencherDemo(demo)"
              >
                {{ demo.papel }}
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const email = ref('admin@reqsys.local')
const senha = ref('admin123')
const mostrarSenha = ref(false)
const carregando = ref(false)
const carregandoMicrosoft = ref(false)
const errMsg = ref('')
const errors = reactive({ email: '', senha: '' })

const demos = [
  { papel: 'Admin', email: 'admin@reqsys.local', senha: 'admin123' },
  { papel: 'Analista', email: 'analista@reqsys.local', senha: 'analista123' },
  { papel: 'Auditor', email: 'auditor@reqsys.local', senha: 'auditor123' },
]

function preencherDemo(demo) {
  email.value = demo.email
  senha.value = demo.senha
}

async function efetuarLogin() {
  errMsg.value = ''
  errors.email = ''
  errors.senha = ''

  if (!email.value) { errors.email = 'Obrigatório'; return }
  if (!senha.value) { errors.senha = 'Obrigatório'; return }

  carregando.value = true
  try {
    await auth.login(email.value, senha.value)
    router.push('/')
  } catch (e) {
    errMsg.value = e?.response?.data?.detail || 'Credenciais inválidas.'
  } finally {
    carregando.value = false
  }
}

async function entrarComMicrosoft() {
  errMsg.value = ''
  carregandoMicrosoft.value = true
  try {
    await auth.loginMicrosoft()
    router.push('/')
  } catch (e) {
    errMsg.value = e?.response?.data?.detail || e?.message || 'Login Microsoft indisponivel.'
  } finally {
    carregandoMicrosoft.value = false
  }
}
</script>

<style scoped>
.login-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 18px 0 14px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 0.75rem;
}

.login-divider::before,
.login-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(var(--v-theme-on-surface), 0.14);
}
</style>
