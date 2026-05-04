<template>
  <main class="login-page">
    <v-card class="login-card" width="440">
      <v-card-title class="d-flex align-center justify-space-between flex-wrap ga-2">
        <span>ReqSys Enterprise</span>
        <v-tooltip text="Ambiente de acesso corporativo com perfil e permissões" location="top">
          <template #activator="{ props }">
            <v-chip v-bind="props" size="small" color="amber" variant="tonal">RBAC</v-chip>
          </template>
        </v-tooltip>
      </v-card-title>
      <v-card-subtitle>Login corporativo com RBAC</v-card-subtitle>
      <form @submit.prevent="entrar">
        <v-card-text>
          <v-alert type="info" variant="tonal" class="mb-4">
            Use as credenciais demo já preenchidas para acessar o ambiente local.
          </v-alert>

          <v-tooltip text="Identidade corporativa usada para autenticação" location="top">
            <template #activator="{ props }">
              <div v-bind="props">
                <v-text-field v-model="email" label="E-mail" variant="outlined" prepend-inner-icon="mdi-email-outline" />
              </div>
            </template>
          </v-tooltip>

          <v-tooltip text="Senha do ambiente de demonstração" location="top">
            <template #activator="{ props }">
              <div v-bind="props">
                <v-text-field
                  v-model="senha"
                  label="Senha"
                  :type="mostrarSenha ? 'text' : 'password'"
                  variant="outlined"
                  prepend-inner-icon="mdi-lock-outline"
                  :append-inner-icon="mostrarSenha ? 'mdi-eye-off' : 'mdi-eye'"
                  @click:append-inner="mostrarSenha = !mostrarSenha"
                />
              </div>
            </template>
          </v-tooltip>

          <v-alert v-if="erro" type="error" density="compact">{{ erro }}</v-alert>
        </v-card-text>
        <v-card-actions>
          <v-tooltip text="Envia as credenciais e inicia a sessão do usuário" location="top">
            <template #activator="{ props }">
              <v-btn v-bind="props" type="submit" block color="amber" :loading="carregando">Entrar</v-btn>
            </template>
          </v-tooltip>
        </v-card-actions>
      </form>
    </v-card>
  </main>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const email = ref('ericsonjosedossantos@tieri659.onmicrosoft.com')
const senha = ref('admin123')
const erro = ref('')
const carregando = ref(false)
const mostrarSenha = ref(false)
const auth = useAuthStore()
const router = useRouter()

async function entrar() {
  carregando.value = true
  erro.value = ''
  try {
    await auth.login({ email: email.value, senha: senha.value })
    router.push('/')
  } catch {
    erro.value = 'Falha no login'
  } finally {
    carregando.value = false
  }
}
</script>

