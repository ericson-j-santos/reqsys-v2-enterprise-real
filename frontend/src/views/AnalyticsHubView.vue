<template>
  <section class="analytics-hub" data-testid="route-analytics" aria-labelledby="titulo-analytics">
    <div class="analytics-header">
      <div>
        <p class="eyebrow">Análise e indicadores</p>
        <h1 id="titulo-analytics">Indicadores</h1>
        <p class="muted">
          Síntese executiva e atalhos para indicadores auditáveis. Saúde de execução, topologia e incidentes ficam concentrados em Monitoramento.
        </p>
      </div>
      <div class="header-actions">
        <SemaforoChip :value="semaforoGeralValor" size="large" />
        <v-btn color="amber" variant="flat" prepend-icon="mdi-refresh" :loading="carregando" @click="carregarTudo">
          Atualizar
        </v-btn>
      </div>
    </div>

    <v-alert
      v-if="erro"
      type="error"
      variant="tonal"
      density="compact"
      role="alert"
      data-testid="analytics-error"
    >
      {{ erro }}
    </v-alert>

    <v-row dense class="mt-2">
      <v-col v-for="card in cardsResumo" :key="card.id" cols="12" sm="6" lg="3">
        <OperationalMetricCard
          :label="card.label"
          :value="card.value"
          :semaforo="card.semaforo"
          :icon="card.icon"
          :hint="card.hint"
          :test-id="`analytics-card-${card.id}`"
          @drilldown="irPara(card.rota)"
        />
      </v-col>
    </v-row>

    <v-card class="panel mt-4" elevation="0" data-testid="analytics-destinations">
      <v-card-title>Detalhamento</v-card-title>
      <v-card-subtitle>
        Cada assunto possui uma fonte canônica. O hub apenas direciona para a área responsável, evitando repetir o mesmo painel em várias telas.
      </v-card-subtitle>
      <v-list density="comfortable" role="presentation">
        <v-list-item
          v-for="destino in destinosAnaliticos"
          :key="destino.path + JSON.stringify(destino.query || {})"
          :prepend-icon="destino.icon"
          :title="destino.title"
          :subtitle="destino.subtitle"
          role="button"
          tabindex="0"
          @click="irPara({ path: destino.path, query: destino.query })"
          @keyup.enter="irPara({ path: destino.path, query: destino.query })"
        />
      </v-list>
    </v-card>
  </section>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import SemaforoChip from '../components/SemaforoChip.vue'
import { useMonitoramentoOperacional } from '../composables/useMonitoramentoOperacional'
import { semaforoGeral } from '../utils/filtrosMonitoramento'

const router = useRouter()
const { carregarMonitoramento, resumoSemaforo, carregando, erro } = useMonitoramentoOperacional()

const semaforoGeralValor = computed(() => {
  const resumo = resumoSemaforo()
  return semaforoGeral({
    verde: resumo.verde || 0,
    amarelo: resumo.amarelo || 0,
    vermelho: resumo.vermelho || 0,
    bloqueado: resumo.bloqueado || 0,
  })
})

const resumoMonitoramento = computed(() => {
  const resumo = resumoSemaforo()
  return {
    verde: resumo.verde || 0,
    amarelo: resumo.amarelo || 0,
    vermelho: resumo.vermelho || 0,
    bloqueados: resumo.bloqueado || 0,
  }
})

const cardsResumo = computed(() => [
  {
    id: 'estatisticas',
    label: 'Estatísticas',
    value: 'Indicadores',
    semaforo: 'verde',
    icon: 'mdi-chart-box-outline',
    hint: 'Indicadores auditáveis com fonte e fórmula',
    rota: { path: '/estatisticas' },
  },
  {
    id: 'financeiro',
    label: 'Financeiro',
    value: 'CDI',
    semaforo: 'verde',
    icon: 'mdi-cash-multiple',
    hint: 'Indicadores financeiros com fonte declarada',
    rota: { path: '/financeiro' },
  },
  {
    id: 'relatorios',
    label: 'Relatórios',
    value: 'Catálogo',
    semaforo: 'verde',
    icon: 'mdi-file-chart-outline',
    hint: 'Relatórios e evidências consolidadas',
    rota: { path: '/relatorios' },
  },
  {
    id: 'operacao',
    label: 'Saúde operacional',
    value: resumoMonitoramento.value.verde + resumoMonitoramento.value.amarelo + resumoMonitoramento.value.vermelho + resumoMonitoramento.value.bloqueados,
    semaforo: semaforoGeralValor.value,
    icon: 'mdi-monitor-dashboard',
    hint: 'Resumo; detalhes ficam no Monitoramento',
    rota: { path: '/monitoramento-operacional' },
  },
])

const destinosAnaliticos = [
  { path: '/estatisticas', icon: 'mdi-chart-box-outline', title: 'Estatísticas', subtitle: 'Fonte, fórmula, tendência e detalhamento dos indicadores' },
  { path: '/financeiro', icon: 'mdi-cash-multiple', title: 'Financeiro', subtitle: 'Indicadores financeiros e respectiva fonte' },
  { path: '/relatorios', icon: 'mdi-file-chart-outline', title: 'Relatórios', subtitle: 'Catálogo de relatórios e evidências' },
  { path: '/govbi-ia', icon: 'mdi-database-search', title: 'GovBI IA', subtitle: 'Consultas analíticas em linguagem natural com controles' },
  { path: '/monitoramento-operacional', query: { estado: 'vermelho' }, icon: 'mdi-monitor-dashboard', title: 'Monitoramento operacional', subtitle: 'Execução, malha, topologia, filas e incidentes — fonte canônica operacional' },
  { path: '/painel-integracao', query: { status: 'erro' }, icon: 'mdi-connection', title: 'Integrações', subtitle: 'Eventos e falhas de conectores na área canônica de integrações' },
]

function irPara(rota) {
  if (!rota?.path) return
  router.push(rota)
}

async function carregarTudo() {
  try {
    await carregarMonitoramento()
  } catch {
    // O composable mantém o estado de erro utilizado pela interface.
  }
}

onMounted(carregarTudo)
</script>

<style scoped>
.analytics-hub { display: flex; flex-direction: column; gap: 8px; padding: var(--space-xs); }
.analytics-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.header-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 var(--space-xs); font-size: var(--font-size-sm); font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--text-muted, #6b7280); }
.panel { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
@media (max-width: 700px) {
  .analytics-header { flex-direction: column; }
  .header-actions { width: 100%; }
}
</style>
