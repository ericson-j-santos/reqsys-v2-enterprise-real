<template>
  <section class="estatisticas-page" data-testid="route-estatisticas" aria-labelledby="titulo-estatisticas">
    <div class="estatisticas-header">
      <div>
        <p class="eyebrow">ReqSys · Analytics próprio</p>
        <h1 id="titulo-estatisticas">Estatísticas</h1>
        <p class="muted">
          Painel de estatísticas internas evidenciadas e informações externas auditáveis, com fonte, fórmula,
          confiabilidade, tendência e pendências explícitas.
        </p>
      </div>
      <v-chip :color="resumo.invalidos ? 'error' : 'success'" variant="tonal" size="large">
        {{ resumo.invalidos ? `${resumo.invalidos} indicador(es) inválido(s)` : 'Guard rails válidos' }}
      </v-chip>
    </div>

    <v-row class="mt-4" dense>
      <v-col v-for="card in cardsResumo" :key="card.id" cols="12" sm="6" lg="2">
        <OperationalMetricCard
          :label="card.label"
          :value="card.value"
          :semaforo="card.semaforo"
          :icon="card.icon"
          :test-id="`estatisticas-card-${card.id}`"
          @drilldown="aplicarFiltroCard(card.filtro)"
        />
      </v-col>
    </v-row>

    <v-card class="panel mt-4" elevation="0">
      <v-card-title>Filtros operacionais</v-card-title>
      <v-card-text>
        <div class="filters">
          <v-select v-model="filtroCategoria" :items="categorias" label="Categoria" clearable variant="outlined" density="comfortable" />
          <v-select v-model="filtroTipoFonte" :items="tiposFonte" label="Tipo de fonte" clearable variant="outlined" density="comfortable" />
          <v-select v-model="filtroEstado" :items="estados" label="Estado atual" clearable variant="outlined" density="comfortable" />
        </div>
      </v-card-text>
    </v-card>

    <v-row class="mt-2" dense>
      <v-col v-for="indicador in indicadoresFiltrados" :key="indicador.id" cols="12" md="6" xl="4">
        <v-card
          class="indicator-card indicator-card--clickable"
          elevation="0"
          role="button"
          tabindex="0"
          :data-testid="`estatisticas-indicador-${indicador.id}`"
          @click="aplicarFiltroCard({ estado: indicador.estadoAtual })"
          @keyup.enter="aplicarFiltroCard({ estado: indicador.estadoAtual })"
          @keyup.space.prevent="aplicarFiltroCard({ estado: indicador.estadoAtual })"
        >
          <v-card-title class="indicator-title">
            <span>{{ indicador.nome }}</span>
            <SemaforoChip :value="estadoParaSemaforo(indicador.estadoAtual)" size="small" />
          </v-card-title>
          <v-card-text>
            <div class="indicator-value">
              <strong>{{ indicador.valorAtual }}{{ indicador.unidade || '' }}</strong>
              <span>{{ indicador.tendencia }}</span>
            </div>
            <p class="muted">{{ indicador.descricao }}</p>
            <dl class="metadata">
              <div><dt>Categoria</dt><dd>{{ indicador.categoria }}</dd></div>
              <div><dt>Fonte</dt><dd>{{ indicador.fonte.nome }} · {{ indicador.fonte.tipo }}</dd></div>
              <div><dt>Coleta</dt><dd>{{ formatarData(indicador.fonte.coletadoEm) }}</dd></div>
              <div><dt>Confiabilidade</dt><dd>{{ indicador.fonte.confiabilidade }}</dd></div>
              <div class="full"><dt>Fórmula</dt><dd>{{ indicador.formula }}</dd></div>
            </dl>
            <v-expansion-panels variant="accordion" class="mt-3">
              <v-expansion-panel title="Analítico e guard rails">
                <v-expansion-panel-text>
                  <h3>Evidências</h3>
                  <ul><li v-for="evidencia in indicador.evidencias" :key="evidencia">{{ evidencia }}</li></ul>
                  <h3>Pendências</h3>
                  <ul><li v-for="pendencia in indicador.pendencias" :key="pendencia">{{ pendencia }}</li></ul>
                  <v-alert v-if="validar(indicador).length" type="warning" variant="tonal" class="mt-3">
                    <strong>Guard rails pendentes</strong>
                    <ul><li v-for="erro in validar(indicador)" :key="erro">{{ erro }}</li></ul>
                  </v-alert>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="panel mt-4" elevation="0">
      <v-card-title>Analítico consolidado</v-card-title>
      <v-card-text>
        <v-table density="compact">
          <thead>
            <tr>
              <th>Indicador</th><th>Categoria</th><th>Valor</th><th>Estado atual</th><th>Estado alvo</th><th>Fonte</th><th>Validação</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="indicador in indicadoresFiltrados" :key="`linha-${indicador.id}`">
              <td>{{ indicador.nome }}</td>
              <td>{{ indicador.categoria }}</td>
              <td>{{ indicador.valorAtual }}{{ indicador.unidade || '' }}</td>
              <td>{{ indicador.estadoAtual }}</td>
              <td>{{ indicador.estadoAlvo }}</td>
              <td>{{ indicador.fonte.tipo }} · {{ indicador.fonte.nome }}</td>
              <td>{{ validar(indicador).length ? 'pendente' : 'válido' }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import SemaforoChip from '../components/SemaforoChip.vue'
import { estadoParaSemaforo } from '../utils/filtrosMonitoramento'
import { calcularResumoEstatisticas, carregarEstatisticas, validarIndicador } from '../services/estatisticas'

const route = useRoute()
const router = useRouter()
const indicadores = ref([])
const filtroCategoria = ref(route.query.categoria || null)
const filtroTipoFonte = ref(route.query.fonte || null)
const filtroEstado = ref(route.query.estado || null)

const resumo = computed(() => calcularResumoEstatisticas(indicadores.value))
const categorias = computed(() => [...new Set(indicadores.value.map((item) => item.categoria))].sort())
const tiposFonte = computed(() => [...new Set(indicadores.value.map((item) => item.fonte?.tipo).filter(Boolean))].sort())
const estados = computed(() => [...new Set(indicadores.value.map((item) => item.estadoAtual))].sort())

const indicadoresFiltrados = computed(() => indicadores.value.filter((item) => {
  if (filtroCategoria.value && item.categoria !== filtroCategoria.value) return false
  if (filtroTipoFonte.value && item.fonte?.tipo !== filtroTipoFonte.value) return false
  if (filtroEstado.value && item.estadoAtual !== filtroEstado.value) return false
  return true
}))

function validar(indicador) {
  return validarIndicador(indicador)
}

const cardsResumo = computed(() => [
  { id: 'total', label: 'Total', value: resumo.value.total, semaforo: 'verde', icon: 'mdi-counter', filtro: {} },
  { id: 'maturidade', label: 'Maturidade média', value: `${resumo.value.maturidadeMedia}%`, semaforo: resumo.value.maturidadeMedia >= 70 ? 'verde' : 'amarelo', icon: 'mdi-chart-arc', filtro: {} },
  { id: 'criticos', label: 'Críticos', value: resumo.value.criticos, semaforo: resumo.value.criticos > 0 ? 'vermelho' : 'verde', icon: 'mdi-alert-circle-outline', filtro: { estado: 'critico' } },
  { id: 'atencao', label: 'Atenção', value: resumo.value.atencao, semaforo: resumo.value.atencao > 0 ? 'amarelo' : 'verde', icon: 'mdi-alert-outline', filtro: { estado: 'atencao' } },
  { id: 'externos', label: 'Externos', value: resumo.value.externos, semaforo: 'verde', icon: 'mdi-earth', filtro: { fonte: 'externa' } },
  { id: 'invalidos', label: 'Inválidos', value: resumo.value.invalidos, semaforo: resumo.value.invalidos > 0 ? 'vermelho' : 'verde', icon: 'mdi-shield-alert-outline', filtro: {} },
])

function aplicarFiltroCard(filtro = {}) {
  if (filtro.estado !== undefined) filtroEstado.value = filtro.estado || null
  if (filtro.categoria !== undefined) filtroCategoria.value = filtro.categoria || null
  if (filtro.fonte !== undefined) filtroTipoFonte.value = filtro.fonte || null
  sincronizarUrl()
}

function sincronizarUrl() {
  const query = {}
  if (filtroCategoria.value) query.categoria = filtroCategoria.value
  if (filtroTipoFonte.value) query.fonte = filtroTipoFonte.value
  if (filtroEstado.value) query.estado = filtroEstado.value
  router.replace({ path: '/estatisticas', query })
}

function formatarData(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}

watch([filtroCategoria, filtroTipoFonte, filtroEstado], sincronizarUrl)

watch(() => route.query, () => {
  filtroCategoria.value = route.query.categoria || null
  filtroTipoFonte.value = route.query.fonte || null
  filtroEstado.value = route.query.estado || null
}, { deep: true })

onMounted(async () => {
  indicadores.value = await carregarEstatisticas()
})
</script>

<style scoped>
.estatisticas-page { display: flex; flex-direction: column; gap: 8px; }
.estatisticas-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--text-muted, #6b7280); }
.panel, .indicator-card { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.indicator-card--clickable { cursor: pointer; transition: transform 0.16s ease, box-shadow 0.16s ease; }
.indicator-card--clickable:hover, .indicator-card--clickable:focus-visible {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
  outline: 2px solid color-mix(in srgb, var(--accent) 45%, transparent);
  outline-offset: 2px;
}
.filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.indicator-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.indicator-value { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.indicator-value strong { font-size: 32px; }
.metadata { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.metadata div { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 10px; }
.metadata .full { grid-column: 1 / -1; }
dt { font-weight: 700; font-size: 12px; color: var(--text-muted, #6b7280); }
dd { margin: 4px 0 0; word-break: break-word; }
ul { padding-left: 18px; }
@media (max-width: 700px) { .metadata { grid-template-columns: 1fr; } .indicator-title, .indicator-value { align-items: flex-start; flex-direction: column; } }
</style>
