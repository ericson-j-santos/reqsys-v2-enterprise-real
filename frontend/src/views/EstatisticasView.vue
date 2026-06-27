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

    <v-tabs v-model="abaAtiva" class="mt-2" color="primary">
      <v-tab value="indicadores">Indicadores</v-tab>
      <v-tab value="projecao">Projeção de Conclusão</v-tab>
    </v-tabs>

    <v-window v-model="abaAtiva" class="mt-4">
      <v-window-item value="indicadores">
        <v-row dense>
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
      </v-window-item>

      <v-window-item value="projecao">
        <v-alert type="info" variant="tonal" class="mb-4">
          <strong>Projeção Estatística de Conclusão</strong> — separa evidenciado de projeção (ADR-022).
          Referência: {{ formatarData(projecao.referencia_temporal) }} · Confiança: {{ projecao.confianca_percentual }}%
        </v-alert>

        <v-row dense>
          <v-col cols="12" sm="6" lg="3">
            <v-card class="metric-card" elevation="0">
              <span>Média dimensões</span>
              <strong>{{ projecao.resumo?.media_dimensoes_percentual }}%</strong>
            </v-card>
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <v-card class="metric-card" elevation="0">
              <span>Conclusão evidenciada</span>
              <strong>{{ projecao.resumo?.media_conclusao_percentual }}%</strong>
            </v-card>
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <v-card class="metric-card" elevation="0">
              <span>Padrão ouro consolidado</span>
              <strong>{{ projecao.resumo?.padrao_ouro_consolidado_percentual }}%</strong>
            </v-card>
          </v-col>
          <v-col cols="12" sm="6" lg="3">
            <v-card class="metric-card" elevation="0">
              <span>Estabilização CI</span>
              <strong>{{ projecao.resumo?.taxa_estabilizacao_ci_percentual }}%</strong>
            </v-card>
          </v-col>
        </v-row>

        <v-card class="panel mt-4" elevation="0">
          <v-card-title>Leitura executiva</v-card-title>
          <v-card-text>
            <p><strong>{{ projecao.leitura_executiva?.fase_atual }}</strong></p>
            <p class="muted">{{ projecao.leitura_executiva?.limitante_principal }}</p>
            <v-chip class="mr-2 mt-2" color="primary" variant="tonal" size="small">Cenário: {{ projecao.cenario_ativo }}</v-chip>
            <v-chip class="mt-2" color="success" variant="tonal" size="small">Modo: {{ projecao.modo }}</v-chip>
          </v-card-text>
        </v-card>

        <v-row class="mt-2" dense>
          <v-col cols="12" lg="6">
            <v-card class="panel" elevation="0">
              <v-card-title>Estado atual consolidado</v-card-title>
              <v-card-text>
                <v-table density="compact">
                  <thead><tr><th>Dimensão</th><th>%</th><th>Maturidade</th></tr></thead>
                  <tbody>
                    <tr v-for="item in projecao.estado_atual_consolidado" :key="item.dimensao">
                      <td>{{ item.dimensao }}</td>
                      <td>{{ item.status_percentual }}%</td>
                      <td>{{ item.maturidade }}</td>
                    </tr>
                  </tbody>
                </v-table>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" lg="6">
            <v-card class="panel" elevation="0">
              <v-card-title>Percentual real de conclusão</v-card-title>
              <v-card-text>
                <v-table density="compact">
                  <thead><tr><th>Indicador</th><th>%</th><th>Tipo</th></tr></thead>
                  <tbody>
                    <tr v-for="item in projecao.percentual_conclusao_real" :key="item.indicador">
                      <td>{{ item.indicador }}</td>
                      <td>{{ item.percentual }}%</td>
                      <td>
                        <v-chip size="x-small" :color="item.tipo === 'evidenciado' ? 'success' : 'warning'" variant="tonal">
                          {{ item.tipo }}
                        </v-chip>
                      </td>
                    </tr>
                  </tbody>
                </v-table>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-row class="mt-2" dense>
          <v-col cols="12" lg="6">
            <v-card class="panel" elevation="0">
              <v-card-title>Gaps restantes</v-card-title>
              <v-card-text>
                <v-table density="compact">
                  <thead><tr><th>Área</th><th>Gap</th></tr></thead>
                  <tbody>
                    <tr v-for="item in projecao.gaps_restantes" :key="item.area">
                      <td>{{ item.area }}</td>
                      <td>{{ item.gap_percentual }}%</td>
                    </tr>
                  </tbody>
                </v-table>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" lg="6">
            <v-card class="panel" elevation="0">
              <v-card-title>Velocidade observada</v-card-title>
              <v-card-text>
                <dl class="metadata">
                  <div>
                    <dt>PRs/dia úteis</dt>
                    <dd>{{ projecao.velocidade_observada?.prs_por_dia_uteis?.min }}–{{ projecao.velocidade_observada?.prs_por_dia_uteis?.max }}</dd>
                  </div>
                  <div>
                    <dt>Merges verdes/dia</dt>
                    <dd>{{ projecao.velocidade_observada?.merges_verdes_por_dia?.min }}–{{ projecao.velocidade_observada?.merges_verdes_por_dia?.max }}</dd>
                  </div>
                  <div>
                    <dt>Lead time PR→merge</dt>
                    <dd>{{ projecao.velocidade_observada?.lead_time_pr_merge_minutos?.min }}–{{ projecao.velocidade_observada?.lead_time_pr_merge_minutos?.max }} min</dd>
                  </div>
                  <div>
                    <dt>Regressão crítica</dt>
                    <dd>{{ projecao.velocidade_observada?.regressao_critica }}</dd>
                  </div>
                </dl>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-row class="mt-2" dense>
          <v-col cols="12" lg="6">
            <v-card class="panel" elevation="0">
              <v-card-title>Projeção de tempo — conservador</v-card-title>
              <v-card-text>
                <v-table density="compact">
                  <thead><tr><th>Marco</th><th>Dias (min–max)</th></tr></thead>
                  <tbody>
                    <tr v-for="item in projecao.projecao_tempo?.conservador" :key="`c-${item.marco}`">
                      <td>{{ item.marco }}</td>
                      <td>{{ item.estimativa_dias_min }}–{{ item.estimativa_dias_max }}</td>
                    </tr>
                  </tbody>
                </v-table>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" lg="6">
            <v-card class="panel" elevation="0">
              <v-card-title>Projeção de tempo — acelerado (recomendado)</v-card-title>
              <v-card-text>
                <v-table density="compact">
                  <thead><tr><th>Marco</th><th>Dias (min–max)</th></tr></thead>
                  <tbody>
                    <tr v-for="item in projecao.projecao_tempo?.acelerado" :key="`a-${item.marco}`">
                      <td>{{ item.marco }}</td>
                      <td>{{ item.estimativa_dias_min }}–{{ item.estimativa_dias_max }}</td>
                    </tr>
                  </tbody>
                </v-table>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-row class="mt-2" dense>
          <v-col cols="12" md="4">
            <v-card class="panel" elevation="0">
              <v-card-title>Probabilidades finais</v-card-title>
              <v-card-text>
                <div v-for="item in projecao.probabilidades_finais" :key="item.resultado" class="prob-item">
                  <span>{{ item.resultado }}</span>
                  <strong>{{ item.probabilidade_percentual }}%</strong>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" md="4">
            <v-card class="panel" elevation="0">
              <v-card-title>Índice de risco</v-card-title>
              <v-card-text>
                <v-table density="compact">
                  <tbody>
                    <tr v-for="item in projecao.indice_risco" :key="item.tipo">
                      <td>{{ item.tipo }}</td>
                      <td>{{ item.nivel }}</td>
                    </tr>
                  </tbody>
                </v-table>
              </v-card-text>
            </v-card>
          </v-col>
          <v-col cols="12" md="4">
            <v-card class="panel" elevation="0">
              <v-card-title>Tendências</v-card-title>
              <v-card-text>
                <v-table density="compact">
                  <tbody>
                    <tr v-for="item in projecao.tendencias" :key="item.indicador">
                      <td>{{ item.indicador }}</td>
                      <td>{{ item.tendencia }}</td>
                    </tr>
                  </tbody>
                </v-table>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-card class="panel mt-4" elevation="0">
          <v-card-title>Gargalos e aceleradores marginais</v-card-title>
          <v-card-text>
            <v-row dense>
              <v-col cols="12" md="6">
                <h3 class="section-subtitle">Gargalos principais</h3>
                <ul><li v-for="item in projecao.gargalos_principais" :key="item">{{ item }}</li></ul>
              </v-col>
              <v-col cols="12" md="6">
                <h3 class="section-subtitle">Maior ganho marginal</h3>
                <ul><li v-for="item in projecao.aceleradores_marginais" :key="item">{{ item }}</li></ul>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { calcularResumoEstatisticas, carregarEstatisticas, carregarProjecaoConclusao, validarIndicador } from '../services/estatisticas'

const abaAtiva = ref('indicadores')
const indicadores = ref([])
const projecao = ref({})
const filtroCategoria = ref(null)
const filtroTipoFonte = ref(null)
const filtroEstado = ref(null)

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

function formatarData(valor) {
  if (!valor) return '-'
  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleString('pt-BR')
}

onMounted(async () => {
  const [indicadoresCarregados, projecaoCarregada] = await Promise.all([
    carregarEstatisticas(),
    carregarProjecaoConclusao()
  ])
  indicadores.value = indicadoresCarregados
  projecao.value = projecaoCarregada
})
</script>

<style scoped>
.estatisticas-page { display: flex; flex-direction: column; gap: 8px; }
.estatisticas-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.eyebrow { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); }
h1 { margin: 0; font-size: clamp(24px, 4vw, 38px); line-height: 1.05; }
.muted { color: var(--text-muted, #6b7280); }
.panel, .metric-card, .indicator-card { border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 16px; }
.metric-card { padding: 16px; height: 100%; }
.metric-card span { display: block; color: var(--text-muted, #6b7280); font-size: 12px; }
.metric-card strong { display: block; margin-top: 8px; font-size: 28px; }
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
.section-subtitle { font-size: 14px; margin: 0 0 8px; }
.prob-item { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.2); }
@media (max-width: 700px) { .metadata { grid-template-columns: 1fr; } .indicator-title, .indicator-value { align-items: flex-start; flex-direction: column; } }
</style>
