<template>
  <v-dialog
    :model-value="modelValue"
    max-width="700"
    scrollable
    aria-label="Busca rápida no ReqSys"
    @update:model-value="atualizarAbertura"
  >
    <v-card data-testid="global-search-dialog">
      <v-card-title class="d-flex align-center justify-space-between">
        <span>Buscar no ReqSys</span>
        <v-btn icon variant="text" aria-label="Fechar busca" data-testid="global-search-close" @click="fechar">
          <v-icon icon="mdi-close" />
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-text-field
          ref="campo"
          v-model="consulta"
          autofocus
          label="O que você procura?"
          placeholder="Ex.: rastreabilidade, projetos, Teams"
          prepend-inner-icon="mdi-magnify"
          density="comfortable"
          variant="outlined"
          clearable
          hide-details
          data-testid="global-search-input"
          @keydown.enter.prevent="abrirPrimeiro"
        />
        <p class="text-caption mt-2 mb-2">
          Pesquise por telas e funcionalidades. Para encontrar registros, use a busca da tela correspondente.
        </p>
        <v-list v-if="resultados.length" density="compact" aria-label="Resultados da busca">
          <v-list-item
            v-for="item in resultados"
            :key="item.to"
            :title="item.title"
            :subtitle="item.temaTitle + ' · ' + item.tip"
            :prepend-icon="item.icon"
            data-testid="global-search-result"
            @click="abrir(item.to)"
          />
        </v-list>
        <v-alert v-else-if="consulta.trim()" type="info" variant="tonal" class="mt-3" data-testid="global-search-empty">
          Nenhuma tela encontrada. Tente outro termo.
        </v-alert>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { NAV_ITEMS_FLAT } from '../constants/navCatalog'
import { buscarNavegacao, filtrarNavegacaoPermitida } from '../utils/globalSearch'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const router = useRouter()
const auth = useAuthStore()
const consulta = ref('')
const campo = ref(null)
const itensPermitidos = computed(() => filtrarNavegacaoPermitida(
  NAV_ITEMS_FLAT,
  (destino) => router.resolve(destino),
  (recurso) => auth.pode(recurso),
))
const resultados = computed(() => buscarNavegacao(consulta.value, itensPermitidos.value))

watch(() => props.modelValue, (aberto) => {
  consulta.value = ''
  if (aberto) nextTick(() => campo.value?.focus())
})

function atualizarAbertura(aberto) {
  emit('update:modelValue', aberto)
}
function fechar() {
  atualizarAbertura(false)
}
async function abrir(destino) {
  fechar()
  await router.push(destino)
}
function abrirPrimeiro() {
  if (resultados.value.length) void abrir(resultados.value[0].to)
}
</script>
