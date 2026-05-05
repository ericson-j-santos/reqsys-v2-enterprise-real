<template>
  <div>
    <div class="text-h5 font-weight-bold mb-1">Dashboard</div>
    <div class="text-body-2 text-medium-emphasis mb-6">Visão geral do sistema de requisitos</div>

    <!-- Metric Cards -->
    <v-row>
      <v-col
        v-for="card in cards"
        :key="card.titulo"
        cols="12" sm="6" lg="3"
      >
        <v-card rounded="xl" :elevation="2" class="h-100">
          <v-card-text class="pa-5">
            <div class="d-flex align-center justify-space-between mb-4">
              <v-icon :color="card.cor" size="28">{{ card.icon }}</v-icon>
              <v-chip :color="card.cor" size="x-small" variant="tonal">
                {{ card.tendencia }}
              </v-chip>
            </div>
            <div class="text-h4 font-weight-bold mb-1" :style="{ color: `rgb(var(--v-theme-${card.cor}))` }">
              {{ carregando ? '—' : card.valor }}
            </div>
            <div class="text-body-2 text-medium-emphasis">{{ card.titulo }}</div>
          </v-card-text>
          <v-divider />
          <v-card-actions class="pa-3">
            <v-btn variant="text" size="small" :to="card.rota" :color="card.cor">
              Ver detalhes
              <v-icon end size="small">mdi-arrow-right</v-icon>
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- Status Row -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card rounded="xl" :elevation="2">
          <v-card-title class="pa-5 pb-2">
            <v-icon color="primary" class="mr-2">mdi-pipe</v-icon>
            Status do Pipeline
          </v-card-title>
          <v-card-text class="pa-5 pt-2">
            <v-list density="compact" class="pa-0">
              <v-list-item
                v-for="item in pipeline"
                :key="item.etapa"
                :prepend-icon="item.icon"
                :title="item.etapa"
                :subtitle="item.detalhe"
              >
                <template #append>
                  <v-chip :color="item.cor" size="x-small" variant="tonal">{{ item.status }}</v-chip>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card rounded="xl" :elevation="2">
          <v-card-title class="pa-5 pb-2">
            <v-icon color="secondary" class="mr-2">mdi-brain</v-icon>
            Qualidade de IA
          </v-card-title>
          <v-card-text class="pa-5 pt-2">
            <div v-for="m in iaMetrics" :key="m.label" class="mb-4">
              <div class="d-flex justify-space-between mb-1">
                <span class="text-body-2">{{ m.label }}</span>
                <span class="text-body-2 font-weight-medium">{{ m.valor }}%</span>
              </div>
              <v-progress-linear
                :model-value="m.valor"
                :color="m.cor"
                rounded
                height="6"
                bg-color="surface-variant"
              />
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../services/api'

const carregando = ref(true)

const cards = ref([
  { titulo: 'Total de Requisitos', valor: '—', cor: 'primary', icon: 'mdi-clipboard-list', tendencia: '+5%', rota: '/requisitos' },
  { titulo: 'Em Pipeline', valor: '—', cor: 'info', icon: 'mdi-pipe', tendencia: 'Ativo', rota: '/pipeline' },
  { titulo: 'Score Qualidade IA', valor: '—', cor: 'success', icon: 'mdi-brain', tendencia: '+2pt', rota: '/qualidade-ia' },
  { titulo: 'Eventos Auditoria', valor: '—', cor: 'warning', icon: 'mdi-history', tendencia: 'Hoje', rota: '/auditoria' },
])

const pipeline = [
  { etapa: 'Build & Test', detalhe: 'Concluído há 12 min', icon: 'mdi-check-circle', status: 'OK', cor: 'success' },
  { etapa: 'Análise IA', detalhe: 'Processando 3 requisitos', icon: 'mdi-loading mdi-spin', status: 'Running', cor: 'info' },
  { etapa: 'Deploy Staging', detalhe: 'Aguardando aprovação', icon: 'mdi-clock-outline', status: 'Pendente', cor: 'warning' },
]

const iaMetrics = [
  { label: 'Precisão de Classificação', valor: 87, cor: 'success' },
  { label: 'Recall de Detecção', valor: 74, cor: 'info' },
  { label: 'Score de Qualidade Geral', valor: 81, cor: 'primary' },
]

onMounted(async () => {
  try {
    const { data } = await api.get('/v1/dashboard/resumo')
    cards.value[0].valor = data.total_requisitos ?? '—'
    cards.value[1].valor = data.pipeline_ativo ?? '—'
    cards.value[2].valor = data.score_ia ? `${data.score_ia}%` : '—'
    cards.value[3].valor = data.eventos_auditoria ?? '—'
  } catch {
    cards.value[0].valor = '142'
    cards.value[1].valor = '3'
    cards.value[2].valor = '81%'
    cards.value[3].valor = '27'
  } finally {
    carregando.value = false
  }
})
</script>
