<template>
  <v-dialog
    :model-value="modelValue"
    max-width="480"
    persistent
    data-testid="confirmacao-ambiente-prod-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="d-flex align-center gap-2">
        <v-icon icon="mdi-alert-circle-outline" color="warning" />
        Abrir produção?
      </v-card-title>
      <v-card-text>
        <p class="mb-2">
          Você está prestes a sair do ambiente atual e abrir a instância de
          <strong>produção</strong>. Será necessário autenticar novamente.
        </p>
        <code v-if="url" class="confirmacao-url">{{ url }}</code>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" data-testid="confirmacao-ambiente-prod-cancelar" @click="$emit('cancelar')">
          Cancelar
        </v-btn>
        <v-btn
          color="warning"
          variant="flat"
          data-testid="confirmacao-ambiente-prod-confirmar"
          @click="$emit('confirmar')"
        >
          Abrir produção
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  url: { type: String, default: '' },
})

defineEmits(['update:modelValue', 'confirmar', 'cancelar'])
</script>

<style scoped>
.confirmacao-url {
  display: block;
  font-size: 12px;
  word-break: break-all;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(148, 163, 184, 0.12);
}
</style>
