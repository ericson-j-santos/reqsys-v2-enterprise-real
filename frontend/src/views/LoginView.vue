<template>
  <main class="login-page">
    <v-card class="login-card" width="440">
      <v-card-title>ReqSys Enterprise</v-card-title>
      <v-card-subtitle>Login corporativo com RBAC</v-card-subtitle>
      <form @submit.prevent="entrar">
        <v-card-text>
          <v-text-field v-model="email" label="E-mail" variant="outlined" />
          <v-text-field v-model="senha" label="Senha" type="password" variant="outlined" />
          <v-alert v-if="erro" type="error" density="compact">{{ erro }}</v-alert>
        </v-card-text>
        <v-card-actions>
          <v-btn type="submit" block color="amber" :loading="carregando">Entrar</v-btn>
        </v-card-actions>
      </form>
    </v-card>
  </main>
</template>
<script setup>
import { ref } from 'vue'; import { useRouter } from 'vue-router'; import { useAuthStore } from '../stores/auth'
const email = ref('ericsonjosedossantos@tieri659.onmicrosoft.com'); const senha = ref('admin123'); const erro = ref(''); const carregando = ref(false)
const auth = useAuthStore(); const router = useRouter()
async function entrar(){ carregando.value=true; erro.value=''; try{ await auth.login({email:email.value, senha:senha.value}); router.push('/') }catch(e){ erro.value='Falha no login' } finally{ carregando.value=false } }
</script>

