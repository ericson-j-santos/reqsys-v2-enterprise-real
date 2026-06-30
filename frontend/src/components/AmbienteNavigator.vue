<template>
  <v-menu location="bottom start" :close-on-content-click="true">
    <template #activator="{ props: menuProps }">
      <button
        type="button"
        class="ambiente-navigator"
        :class="{ 'ambiente-navigator--compact': compact }"
        v-bind="menuProps"
        :aria-label="`Ambiente atual: ${ambienteAtualLabel}. Clique para trocar de ambiente.`"
        :data-testid="testId"
      >
        <span v-if="showPrefix">Ambiente:</span>
        <strong>{{ ambienteAtualLabel }}</strong>
        <v-icon icon="mdi-chevron-down" size="14" class="ambiente-navigator__icon" />
      </button>
    </template>

    <v-list density="compact" class="ambiente-navigator-menu" data-testid="ambiente-navigator-menu">
      <v-list-subheader>Trocar ambiente</v-list-subheader>
      <v-list-item
        v-for="item in opcoes"
        :key="item.id"
        :disabled="item.id === ambienteAtualId"
        :data-testid="`ambiente-opcao-${item.shortId}`"
        @click="selecionar(item.id)"
      >
        <template #prepend>
          <v-chip size="x-small" :color="item.color" variant="tonal">{{ item.label }}</v-chip>
        </template>
        <v-list-item-title>{{ item.frontend.replace(/^https?:\/\//, '') }}</v-list-item-title>
        <v-list-item-subtitle v-if="item.id === ambienteAtualId">Você está aqui</v-list-item-subtitle>
        <v-list-item-subtitle v-else-if="item.id === 'producao'">Requer confirmação</v-list-item-subtitle>
        <v-list-item-subtitle v-else>Abrir esta instância</v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-menu>

  <ConfirmacaoAmbienteProducaoDialog
    v-model="confirmacaoProdAberta"
    :url="destinoPendente?.url || ''"
    @confirmar="confirmarNavegacaoProd"
    @cancelar="cancelarNavegacaoProd"
  />
</template>

<script setup>
import { computed } from 'vue'
import ConfirmacaoAmbienteProducaoDialog from './ConfirmacaoAmbienteProducaoDialog.vue'
import { useNavegacaoAmbiente } from '../composables/useNavegacaoAmbiente'
import {
  ambientesNavegaveis,
  labelAmbiente,
  resolverAmbienteAtual,
} from '../constants/ambientesOperacionais'

const props = defineProps({
  environmentHint: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  showPrefix: { type: Boolean, default: true },
  testId: { type: String, default: 'ambiente-navigator' },
})

const hostname = typeof window !== 'undefined' ? window.location.hostname : ''

const ambienteAtualId = computed(() =>
  resolverAmbienteAtual({ environmentHint: props.environmentHint, hostname }),
)

const ambienteAtualLabel = computed(() => labelAmbiente(ambienteAtualId.value))

const opcoes = computed(() => ambientesNavegaveis({ hostname }))

const {
  confirmacaoProdAberta,
  destinoPendente,
  solicitarNavegacao,
  confirmarNavegacaoProd,
  cancelarNavegacaoProd,
} = useNavegacaoAmbiente()

function selecionar(id) {
  if (id === ambienteAtualId.value) return
  solicitarNavegacao(id, { preserveRoute: true })
}
</script>

<style scoped>
.ambiente-navigator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--radius-pill);
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 700;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.ambiente-navigator:hover,
.ambiente-navigator[aria-expanded='true'] {
  border-color: var(--accent);
  background: rgba(245, 158, 11, 0.08);
}

.ambiente-navigator--compact {
  padding: 4px 10px;
  font-size: 11px;
}

.ambiente-navigator__icon {
  opacity: 0.75;
}

.ambiente-navigator-menu {
  min-width: 280px;
}
</style>
