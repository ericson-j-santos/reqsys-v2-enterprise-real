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
      <form @submit.prevent="entrar">
        <v-card-text>
          <v-alert type="info" variant="tonal" class="mb-4">
            Use as credenciais demo já preenchidas para acessar o ambiente cloud.
          </v-alert>

          <v-text-field
            v-model="email"
            label="E-mail"
            variant="outlined"
            prepend-inner-icon="mdi-email-outline"
            class="mb-2"
          />

          <v-text-field
            v-model="senha"
            label="Senha"
            :type="mostrarSenha ? 'text' : 'password'"
            variant="outlined"
            prepend-inner-icon="mdi-lock-outline"
            :append-inner-icon="mostrarSenha ? 'mdi-eye-off' : 'mdi-eye'"
            @click:append-inner="mostrarSenha = !mostrarSenha"
          />

          <v-alert v-if="erro" type="error" density="compact" class="mt-1">{{ erro }}</v-alert>
        </v-card-text>
        <v-card-actions class="px-4 pb-4">
          <v-btn type="submit" block color="amber" :loading="carregando" size="large">Entrar</v-btn>
        </v-card-actions>
      </form>
    </v-card>
  </main>
</template>
<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { useAuthStore } from '../stores/auth'

const { width } = useDisplay()
const cardWidth = computed(() => Math.min(440, width.value - 32))

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
</style>

