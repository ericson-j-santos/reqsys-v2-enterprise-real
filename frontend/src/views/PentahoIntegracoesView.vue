<template>
  <section class="pentaho-integracoes pa-4">
    <div class="d-flex flex-wrap align-center justify-space-between ga-3 mb-4">
      <div>
        <h1 class="text-h4">Integrações &gt; Pentaho</h1>
        <p class="text-medium-emphasis mb-0">Acompanhamento de lotes, processamento e quarentena.</p>
      </div>
      <v-btn :loading="carregando" prepend-icon="mdi-refresh" variant="tonal" @click="carregar">
        Atualizar
      </v-btn>
    </div>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4">{{ erro }}</v-alert>

    <v-row>
      <v-col cols="12" sm="6" md="3">
        <v-card elevation="0" border><v-card-text><div class="text-caption">Recebidos hoje</div><div class="text-h4">{{ contagens.recebidos }}</div></v-card-text></v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card elevation="0" border><v-card-text><div class="text-caption">Concluídos</div><div class="text-h4">{{ contagens.concluidos }}</div></v-card-text></v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card elevation="0" border><v-card-text><div class="text-caption">Em processamento</div><div class="text-h4">{{ contagens.processando }}</div></v-card-text></v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card elevation="0" border><v-card-text><div class="text-caption">Quarentena</div><div class="text-h4">{{ contagens.quarentena }}</div></v-card-text></v-card>
      </v-col>
    </v-row>

    <v-card class="mt-4" elevation="0" border>
      <v-card-title>Últimos processos</v-card-title>
      <v-card-text>
        <v-table density="compact">
          <thead><tr><th>Processo</th><th>Situação</th><th>Última execução</th><th>Lote</th></tr></thead>
          <tbody>
            <tr v-for="item in processos" :key="item.processo">
              <td>{{ item.processo }}</td>
              <td><v-chip size="small" :color="corStatus(item.status)" variant="tonal">{{ rotuloStatus(item.status) }}</v-chip></td>
              <td>{{ formatarData(item.ultimaExecucao) }}</td>
              <td class="text-truncate" style="max-width: 260px">{{ item.loteId }}</td>
            </tr>
            <tr v-if="!processos.length"><td colspan="4" class="text-medium-emphasis">Nenhum processo recebido.</td></tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>

    <v-card class="mt-4" elevation="0" border>
      <v-card-title>Lotes recentes</v-card-title>
      <v-card-text>
        <v-table density="compact">
          <thead>
            <tr><th>Processo</th><th>Lote</th><th>Situação</th><th>Recebidos</th><th>Aceitos</th><th>Rejeitados</th><th>Tentativas</th><th>Ação</th></tr>
          </thead>
          <tbody>
            <tr v-for="lote in lotes" :key="lote.loteId">
              <td>{{ lote.processo }}</td>
              <td>{{ lote.lote || lote.loteId }}</td>
              <td><v-chip size="small" :color="corStatus(lote.status)" variant="tonal">{{ rotuloStatus(lote.status) }}</v-chip></td>
              <td>{{ lote.registrosRecebidos }}</td>
              <td>{{ lote.registrosAceitos }}</td>
              <td>{{ lote.registrosRejeitados }}</td>
              <td>{{ lote.tentativas }}</td>
              <td>
                <v-btn
                  v-if="lote.status === 'QUARENTENA'"
                  size="small"
                  variant="text"
                  :loading="reprocessando === lote.loteId"
                  @click="reprocessar(lote.loteId)"
                >Reprocessar</v-btn>
                <span v-else>—</span>
              </td>
            </tr>
            <tr v-if="!lotes.length"><td colspan="8" class="text-medium-emphasis">Nenhum lote disponível.</td></tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { carregarPainelPentaho, reprocessarLotePentaho } from '../services/pentahoIntegration'

const painel = ref(null)
const carregando = ref(false)
const erro = ref('')
const reprocessando = ref('')

const contagens = computed(() => painel.value?.contagens || { recebidos: 0, concluidos: 0, processando: 0, quarentena: 0 })
const processos = computed(() => painel.value?.processos || [])
const lotes = computed(() => painel.value?.lotesRecentes || [])

function rotuloStatus(status) {
  return ({ PENDENTE: 'Pendente', PROCESSANDO: 'Processando', CONCLUIDO: 'Concluído', QUARENTENA: 'Quarentena' })[status] || status || 'Desconhecido'
}

function corStatus(status) {
  return ({ PENDENTE: 'warning', PROCESSANDO: 'info', CONCLUIDO: 'success', QUARENTENA: 'error' })[status] || undefined
}

function formatarData(valor) {
  if (!valor) return '—'
  const data = new Date(valor)
  return Number.isNaN(data.getTime()) ? valor : data.toLocaleString('pt-BR')
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    painel.value = await carregarPainelPentaho(30)
  } catch (e) {
    erro.value = e?.response?.data?.detail || 'Não foi possível carregar o painel de integrações Pentaho.'
  } finally {
    carregando.value = false
  }
}

async function reprocessar(loteId) {
  reprocessando.value = loteId
  erro.value = ''
  try {
    await reprocessarLotePentaho(loteId)
    await carregar()
  } catch (e) {
    erro.value = e?.response?.data?.detail || 'Não foi possível reprocessar o lote.'
  } finally {
    reprocessando.value = ''
  }
}

onMounted(carregar)
</script>
