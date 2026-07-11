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
    Use o menu lateral para acessar uma tela disponível para o seu papel.
  </v-alert>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const forbiddenResource = computed(() => {
  const value = route.query.forbidden
  return typeof value === 'string' ? value : ''
})
</script>
