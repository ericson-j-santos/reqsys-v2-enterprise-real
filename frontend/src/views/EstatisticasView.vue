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

    <v-card v-if="projecaoConclusao" class="projection-panel mt-4" elevation="0">
      <v-card-text>
        <div class="projection-header">
          <div>
            <p class="eyebrow">ReqSys · Projeção estatística de conclusão</p>
            <h2>{{ leituraExecutiva.posicionamento }}</h2>
            <p class="muted">
              Referência temporal: {{ formatarData(projecaoConclusao.referenciaTemporal) }} · Origem versionada:
              {{ projecaoConclusao.origem }}
            </p>
          </div>
          <v-chip color="primary" variant="tonal" size="large">
            Padrão ouro atual {{ projecaoConclusao.resumo.padraoOuroAtual }}%
          </v-chip>
        </div>

        <div class="projection-actions">
          <v-btn color="primary" variant="tonal" to="/pipeline">Pipeline</v-btn>
          <v-btn color="secondary" variant="tonal" to="/monitoramento-operacional">Monitoramento</v-btn>
        </div>

        <v-row class="mt-4" dense>
          <v-col cols="12" sm="6" lg="3">
            <div class="projection-metric">
              <span>Maturidade média</span>
              <strong>{{ projecaoConclusao.resumo.maturidadeMediaDimensoes }}%</strong>
            </div>
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <div class="projection-metric">
              <span>MVP forte &lt; 1 semana</span>
              <strong>{{ projecaoConclusao.resumo.probabilidadeMvpSemana }}%</strong>
            </div>
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <div class="projection-metric">
              <span>Produção enterprise</span>
              <strong>{{ projecaoConclusao.resumo.probabilidadeProducaoEnterprise }}%</strong>
            </div>
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <div class="projection-metric">
              <span>Janela MVP acelerada</span>
              <strong>{{ projecaoConclusao.resumo.janelaMvpAcelerada }}</strong>
            </div>
          </v-col>
        </v-row>

        <v-row class="mt-4" dense>
          <v-col v-for="cenario in projecaoConclusao.cenarios" :key="cenario.id" cols="12" lg="6">
            <div class="scenario-card">
              <div class="scenario-header">
                <div>
                  <h3>{{ cenario.nome }}</h3>
                  <p class="muted">{{ cenario.descricao }}</p>
                </div>
              </div>
              <ul class="scenario-list">
                <li v-for="marco in cenario.marcos" :key="marco.id">
                  <span>{{ marco.nome }}</span>
                  <strong>{{ marco.faixaDias }}</strong>
                </li>
              </ul>
            </div>
          </v-col>
        </v-row>

        <v-row class="mt-4" dense>
          <v-col cols="12">
            <div class="subpanel">
              <h3>Velocidade observada</h3>
              <div class="pill-list">
                <v-chip v-for="velocidade in projecaoConclusao.velocidadeAtual" :key="velocidade.id" color="info" variant="tonal" size="small">
                  {{ velocidade.nome }}: {{ velocidade.valorTexto }} {{ velocidade.unidade }}
                </v-chip>
              </div>
            </div>
          </v-col>
        </v-row>

        <v-row class="mt-4" dense>
          <v-col cols="12" md="4">
            <div class="subpanel">
              <h3>Maiores gaps</h3>
              <ul class="compact-list">
                <li v-for="gap in maioresGaps" :key="gap.id">
                  <span>{{ gap.nome }}</span>
                  <strong>{{ gap.percentual }}%</strong>
                </li>
              </ul>
            </div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="subpanel">
              <h3>Gargalos prioritários</h3>
              <div class="pill-list">
                <v-chip v-for="gargalo in projecaoConclusao.principaisGargalos" :key="gargalo" color="warning" variant="tonal" size="small">
                  {{ gargalo }}
                </v-chip>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="subpanel">
              <h3>Aceleradores</h3>
              <div class="pill-list">
                <v-chip v-for="acelerador in projecaoConclusao.aceleradores" :key="acelerador" color="success" variant="tonal" size="small">
                  {{ acelerador }}
                </v-chip>
              </div>
            </div>
          </v-col>
        </v-row>

        <v-row class="mt-4" dense>
          <v-col cols="12" md="6">
            <div class="subpanel">
              <h3>Riscos e tendências</h3>
              <div class="stack-list">
                <div v-for="risco in projecaoConclusao.riscos" :key="risco.id" class="stack-item">
                  <span>{{ risco.tipo }}</span>
                  <v-chip :color="corRisco(risco.nivel)" variant="tonal" size="small">{{ rotuloLegivel(risco.nivel) }}</v-chip>
                </div>
                <div v-for="tendencia in projecaoConclusao.tendencias" :key="tendencia.id" class="stack-item">
                  <span>{{ tendencia.nome }}</span>
                  <v-chip :color="corTendencia(tendencia.tendencia)" variant="tonal" size="small">{{ rotuloLegivel(tendencia.tendencia) }}</v-chip>
                </div>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="6">
            <div class="subpanel">
              <h3>Leitura executiva</h3>
              <p class="muted">
                O projeto já opera como arquitetura enterprise funcional em aceleração contínua; o ganho marginal agora
                vem de sincronização, evidência automática e hardening final.
              </p>
              <div class="two-column-list">
                <div>
                  <h4>Forças atuais</h4>
                  <ul>
                    <li v-for="forca in leituraExecutiva.forcas" :key="forca">{{ forca }}</li>
                  </ul>
                </div>
                <div>
                  <h4>Falta consolidar</h4>
                  <ul>
                    <li v-for="faltante in leituraExecutiva.faltantes" :key="faltante">{{ faltante }}</li>
                  </ul>
                </div>
              </div>
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

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
import { computed, onMounted, ref } from 'vue'
import { calcularResumoEstatisticas, carregarSnapshotEstatisticas, validarIndicador } from '../services/estatisticas'

const snapshot = ref({ indicadores: [], projecaoConclusao: null })
const filtroCategoria = ref(null)
const filtroTipoFonte = ref(null)
const filtroEstado = ref(null)

const indicadores = computed(() => snapshot.value.indicadores || [])
const projecaoConclusao = computed(() => snapshot.value.projecaoConclusao)
const leituraExecutiva = computed(() => projecaoConclusao.value?.leituraExecutiva || { posicionamento: '', forcas: [], faltantes: [] })
const maioresGaps = computed(() => [...(projecaoConclusao.value?.gapRestante || [])].sort((a, b) => b.percentual - a.percentual).slice(0, 3))
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

function corEstado(estado) {
  if (estado === 'critico') return 'error'
  if (estado === 'atencao' || estado === 'nao_medido') return 'warning'
  if (estado === 'avancado') return 'primary'
  return 'success'
}

function corRisco(nivel) {
  if (nivel === 'medio') return 'warning'
  if (nivel === 'medio_baixo') return 'secondary'
  return 'success'
}

function corTendencia(tendencia) {
  if (tendencia === 'forte_alta') return 'success'
  if (tendencia === 'moderada_alta') return 'primary'
  return 'secondary'
}

function rotuloLegivel(valor) {
  return String(valor || '-').replaceAll('_', ' ')
}

function formatarData(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}

onMounted(async () => {
  snapshot.value = await carregarSnapshotEstatisticas()
})
</script>

<style scoped>
.estatisticas-page { display: flex; flex-direction: column; gap: 8px; }
.estatisticas-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
h2, h3, h4 { margin: 0; }
.muted { color: var(--text-muted, #6b7280); }
.panel, .metric-card, .indicator-card, .projection-panel, .projection-metric, .scenario-card, .subpanel { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.metric-card { padding: 16px; height: 100%; }
.metric-card span { display: block; color: var(--text-muted, #6b7280); font-size: 12px; }
.metric-card strong { display: block; margin-top: 8px; font-size: 28px; }
.filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.indicator-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.indicator-value { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.indicator-value strong { font-size: 32px; }
.projection-panel { background: linear-gradient(180deg, rgba(15, 23, 42, 0.02), rgba(15, 23, 42, 0)); }
.projection-header, .scenario-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.projection-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.projection-metric, .subpanel, .scenario-card { padding: 16px; height: 100%; }
.projection-metric span { display: block; color: var(--text-muted, #6b7280); font-size: 12px; }
.projection-metric strong { display: block; margin-top: 8px; font-size: 28px; }
.scenario-list, .compact-list { list-style: none; padding: 0; margin: 16px 0 0; display: grid; gap: 10px; }
.scenario-list li, .compact-list li, .stack-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 10px; }
.pill-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.stack-list { display: grid; gap: 10px; margin-top: 12px; }
.two-column-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }
.metadata { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.metadata div { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 10px; }
.metadata .full { grid-column: 1 / -1; }
dt { font-weight: 700; font-size: 12px; color: var(--text-muted, #6b7280); }
dd { margin: 4px 0 0; word-break: break-word; }
ul { padding-left: 18px; }
@media (max-width: 700px) {
  .metadata, .two-column-list { grid-template-columns: 1fr; }
  .indicator-title, .indicator-value, .projection-header { align-items: flex-start; flex-direction: column; }
}
</style>
