<template>
  <section class="estatisticas-page" aria-labelledby="titulo-estatisticas">
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
      <v-col cols="12" sm="6" lg="2">
        <v-card class="metric-card" elevation="0"><span>Total</span><strong>{{ resumo.total }}</strong></v-card>
      </v-col>
      <v-col cols="12" sm="6" lg="2">
        <v-card class="metric-card" elevation="0"><span>Maturidade média</span><strong>{{ resumo.maturidadeMedia }}%</strong></v-card>
      </v-col>
      <v-col cols="12" sm="6" lg="2">
        <v-card class="metric-card" elevation="0"><span>Críticos</span><strong>{{ resumo.criticos }}</strong></v-card>
      </v-col>
      <v-col cols="12" sm="6" lg="2">
        <v-card class="metric-card" elevation="0"><span>Atenção</span><strong>{{ resumo.atencao }}</strong></v-card>
      </v-col>
      <v-col cols="12" sm="6" lg="2">
        <v-card class="metric-card" elevation="0"><span>Externos</span><strong>{{ resumo.externos }}</strong></v-card>
      </v-col>
      <v-col cols="12" sm="6" lg="2">
        <v-card class="metric-card" elevation="0"><span>Inválidos</span><strong>{{ resumo.invalidos }}</strong></v-card>
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
        <v-card class="indicator-card" elevation="0">
          <v-card-title class="indicator-title">
            <span>{{ indicador.nome }}</span>
            <v-chip size="small" :color="corEstado(indicador.estadoAtual)" variant="tonal">{{ indicador.estadoAtual }}</v-chip>
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
            <v-btn
              class="mt-3"
              color="primary"
              variant="tonal"
              block
              :aria-label="`Abrir drill-down do indicador ${indicador.nome}`"
              @click="abrirDrilldown(indicador)"
            >
              Abrir drill-down
            </v-btn>
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
              <th>Indicador</th><th>Categoria</th><th>Valor</th><th>Estado atual</th><th>Estado alvo</th><th>Fonte</th><th>Validação</th><th>Ação</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="indicador in indicadoresFiltrados"
              :key="`linha-${indicador.id}`"
              class="linha-drilldown"
              tabindex="0"
              role="button"
              :aria-label="`Abrir drill-down do indicador ${indicador.nome}`"
              @click="abrirDrilldown(indicador)"
              @keydown.enter.prevent="abrirDrilldown(indicador)"
              @keydown.space.prevent="abrirDrilldown(indicador)"
            >
              <td>{{ indicador.nome }}</td>
              <td>{{ indicador.categoria }}</td>
              <td>{{ indicador.valorAtual }}{{ indicador.unidade || '' }}</td>
              <td>{{ indicador.estadoAtual }}</td>
              <td>{{ indicador.estadoAlvo }}</td>
              <td>{{ indicador.fonte.tipo }} · {{ indicador.fonte.nome }}</td>
              <td>{{ validar(indicador).length ? 'pendente' : 'válido' }}</td>
              <td><v-chip size="small" color="primary" variant="tonal">drill-down</v-chip></td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>

    <v-dialog v-model="dialogDrilldown" max-width="860" scrollable>
      <v-card v-if="drilldownSelecionado" class="drilldown-card" elevation="0">
        <v-card-title class="drilldown-title">
          <div>
            <p class="eyebrow">Drill-down operacional</p>
            <h2>{{ drilldownSelecionado.titulo }}</h2>
          </div>
          <v-chip :color="drilldownSelecionado.statusNavegavel === 'operacional' ? 'success' : 'warning'" variant="tonal">
            {{ drilldownSelecionado.statusNavegavel }}
          </v-chip>
        </v-card-title>
        <v-card-text>
          <v-row dense>
            <v-col cols="12" sm="6" md="3"><div class="drilldown-kpi"><span>Valor</span><strong>{{ drilldownSelecionado.valorAtual }}</strong></div></v-col>
            <v-col cols="12" sm="6" md="3"><div class="drilldown-kpi"><span>Estado atual</span><strong>{{ drilldownSelecionado.estadoAtual }}</strong></div></v-col>
            <v-col cols="12" sm="6" md="3"><div class="drilldown-kpi"><span>Estado alvo</span><strong>{{ drilldownSelecionado.estadoAlvo }}</strong></div></v-col>
            <v-col cols="12" sm="6" md="3"><div class="drilldown-kpi"><span>Tendência</span><strong>{{ drilldownSelecionado.tendencia }}</strong></div></v-col>
          </v-row>

          <v-alert class="mt-4" type="info" variant="tonal">
            <strong>Próxima ação:</strong> {{ drilldownSelecionado.proximaAcao }}
          </v-alert>

          <dl class="metadata mt-4">
            <div><dt>Categoria</dt><dd>{{ drilldownSelecionado.categoria }}</dd></div>
            <div><dt>Fonte</dt><dd>{{ drilldownSelecionado.fonte.nome }} · {{ drilldownSelecionado.fonte.tipo }}</dd></div>
            <div><dt>Origem</dt><dd>{{ drilldownSelecionado.fonte.origem }}</dd></div>
            <div><dt>Confiabilidade</dt><dd>{{ drilldownSelecionado.fonte.confiabilidade }}</dd></div>
            <div><dt>Coleta</dt><dd>{{ formatarData(drilldownSelecionado.fonte.coletadoEm) }}</dd></div>
            <div><dt>Versão conector</dt><dd>{{ drilldownSelecionado.fonte.versaoConector }}</dd></div>
            <div class="full"><dt>Fórmula</dt><dd>{{ drilldownSelecionado.formula }}</dd></div>
          </dl>

          <v-row class="mt-3" dense>
            <v-col cols="12" md="4">
              <v-card class="drilldown-section" elevation="0">
                <v-card-title>Evidências</v-card-title>
                <v-card-text><ul><li v-for="item in drilldownSelecionado.evidencias" :key="item">{{ item }}</li></ul></v-card-text>
              </v-card>
            </v-col>
            <v-col cols="12" md="4">
              <v-card class="drilldown-section" elevation="0">
                <v-card-title>Pendências</v-card-title>
                <v-card-text><ul><li v-for="item in drilldownSelecionado.pendencias" :key="item">{{ item }}</li></ul></v-card-text>
              </v-card>
            </v-col>
            <v-col cols="12" md="4">
              <v-card class="drilldown-section" elevation="0">
                <v-card-title>Guard rails</v-card-title>
                <v-card-text>
                  <p v-if="!drilldownSelecionado.guardRails.length" class="muted">Sem violação de contrato.</p>
                  <ul><li v-for="item in drilldownSelecionado.guardRails" :key="item">{{ item }}</li></ul>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>

          <v-card class="drilldown-section mt-3" elevation="0">
            <v-card-title>Trilha de auditoria navegável</v-card-title>
            <v-card-text>
              <v-chip-group>
                <v-chip v-for="item in drilldownSelecionado.trilhaAuditoria" :key="item" size="small" variant="tonal">
                  {{ item }}
                </v-chip>
              </v-chip-group>
            </v-card-text>
          </v-card>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="fecharDrilldown">Fechar</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { calcularResumoEstatisticas, carregarEstatisticas, criarDrilldownIndicador, validarIndicador } from '../services/estatisticas'

const indicadores = ref([])
const filtroCategoria = ref(null)
const filtroTipoFonte = ref(null)
const filtroEstado = ref(null)
const dialogDrilldown = ref(false)
const drilldownSelecionado = ref(null)

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

function abrirDrilldown(indicador) {
  drilldownSelecionado.value = criarDrilldownIndicador(indicador)
  dialogDrilldown.value = true
}

function fecharDrilldown() {
  dialogDrilldown.value = false
}

function corEstado(estado) {
  if (estado === 'critico') return 'error'
  if (estado === 'atencao' || estado === 'nao_medido') return 'warning'
  if (estado === 'avancado') return 'primary'
  return 'success'
}

function formatarData(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}

onMounted(async () => {
  indicadores.value = await carregarEstatisticas()
})
</script>

<style scoped>
.estatisticas-page { display: flex; flex-direction: column; gap: 8px; }
.estatisticas-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1, h2 { margin: 0; line-height: 1.05; }
h1 { font-size: clamp(24px, 4vw, 38px); }
h2 { font-size: clamp(20px, 3vw, 30px); }
.muted { color: var(--text-muted, #6b7280); }
.panel, .metric-card, .indicator-card, .drilldown-card, .drilldown-kpi, .drilldown-section { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.metric-card { padding: 16px; height: 100%; }
.metric-card span, .drilldown-kpi span { display: block; color: var(--text-muted, #6b7280); font-size: 12px; }
.metric-card strong { display: block; margin-top: 8px; font-size: 28px; }
.drilldown-kpi { padding: 14px; height: 100%; }
.drilldown-kpi strong { display: block; margin-top: 6px; font-size: 20px; word-break: break-word; }
.filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.indicator-title, .drilldown-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.indicator-value { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.indicator-value strong { font-size: 32px; }
.metadata { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.metadata div { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 10px; }
.metadata .full { grid-column: 1 / -1; }
.linha-drilldown { cursor: pointer; }
.linha-drilldown:hover { background: rgba(148, 163, 184, 0.08); }
.linha-drilldown:focus { outline: 2px solid var(--accent); outline-offset: -2px; }
dt { font-weight: 700; font-size: 12px; color: var(--text-muted, #6b7280); }
dd { margin: 4px 0 0; word-break: break-word; }
ul { padding-left: 18px; }
@media (max-width: 700px) { .metadata { grid-template-columns: 1fr; } .indicator-title, .indicator-value, .drilldown-title { align-items: flex-start; flex-direction: column; } }
</style>
