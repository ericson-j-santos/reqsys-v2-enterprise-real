<template>
  <section class="page" data-testid="route-govbi-ia">
    <PageHeader
      title="GovBI IA"
      subtitle="Consultas analíticas em linguagem natural com BI governado por inteligência artificial."
      chip="Beta"
      chip-color="blue"
      chip-tooltip="Integração com GovBI IA via proxy governado do backend ReqSys"
    >
      <template #actions>
        <v-btn
          size="small"
          variant="outlined"
          prepend-icon="mdi-clipboard-check-outline"
          :loading="verificandoFuncionamento"
          data-testid="govbi-reexecutar-funcionamento"
          @click="executarVerificacaoFuncionamento"
        >
          Testes
        </v-btn>
        <v-btn
          size="small"
          variant="outlined"
          prepend-icon="mdi-refresh"
          :loading="carregando"
          @click="limpar"
        >
          Limpar
        </v-btn>
      </template>
    </PageHeader>

    <v-card class="table-card mb-4" data-testid="govbi-painel-funcionamento">
      <v-card-title class="d-flex align-center flex-wrap gap-2">
        <span>Painel de funcionamento</span>
        <v-chip
          size="small"
          :color="funcionamentoResumo.completo ? 'green' : funcionamentoResumo.percentual > 0 ? 'orange' : 'grey'"
          variant="tonal"
          data-testid="govbi-funcionamento-percentual"
        >
          {{ funcionamentoResumo.percentual }}% ({{ funcionamentoResumo.aprovados }}/{{ funcionamentoResumo.total }})
        </v-chip>
        <v-spacer />
        <span class="text-caption muted" data-testid="govbi-funcionamento-executado-em">
          {{ funcionamentoExecutadoEmLabel }}
        </span>
      </v-card-title>
      <v-divider />
      <v-card-text>
        <v-alert
          v-if="verificandoFuncionamento"
          type="info"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          Executando testes de funcionamento GovBI (local + API)…
        </v-alert>
        <div class="responsive-table-shell">
          <v-data-table
            :headers="funcionamentoHeaders"
            :items="funcionamentoResumo.resultados"
            density="compact"
            :items-per-page="20"
            hide-default-footer
            data-testid="govbi-funcionamento-tabela"
          >
            <template #item.ok="{ item }">
              <v-chip
                size="x-small"
                :color="item.ok ? 'green' : 'red'"
                variant="tonal"
                :data-testid="`govbi-teste-${item.id}`"
              >
                {{ item.ok ? 'OK' : 'Falha' }}
              </v-chip>
            </template>
            <template #item.categoria="{ item }">
              <v-chip size="x-small" variant="outlined">{{ item.categoria }}</v-chip>
            </template>
          </v-data-table>
        </div>
      </v-card-text>
    </v-card>

    <div v-if="historicoConsultas.length" class="metrics-grid mb-4" data-testid="govbi-metrics-grid">
      <OperationalMetricCard
        v-for="metric in metricasGovbi"
        :key="metric.id"
        :label="metric.label"
        :value="metric.value"
        :semaforo="metric.semaforo"
        :icon="metric.icon"
        :hint="metric.hint"
        :test-id="`govbi-metric-${metric.id}`"
        @drilldown="aplicarFiltroMetrica(metric.filtros)"
      />
    </div>

    <v-card class="table-card mb-4">
      <v-card-text>
        <v-textarea
          v-model="pergunta"
          label="Faça uma pergunta analítica"
          placeholder="Ex: Quantas propostas foram cadastradas em 2024 por unidade?"
          rows="3"
          auto-grow
          clearable
          :disabled="carregando"
          @keydown.ctrl.enter="perguntar"
        />
        <div class="d-flex align-center gap-3 mt-2 flex-wrap">
          <v-checkbox
            v-model="exibirSql"
            label="Mostrar SQL gerado"
            density="compact"
            hide-details
          />
          <v-spacer />
          <span class="muted" style="font-size:0.78rem">Ctrl+Enter para enviar</span>
          <v-btn
            color="amber"
            variant="tonal"
            prepend-icon="mdi-robot-outline"
            :loading="carregando"
            :disabled="!pergunta.trim()"
            @click="perguntar"
          >
            Analisar
          </v-btn>
        </div>
      </v-card-text>
    </v-card>

    <v-alert v-if="erro" type="error" variant="tonal" class="mb-4" closable @click:close="erro = ''">
      {{ erro }}
    </v-alert>

    <v-alert
      v-if="diagnosticoOperacional"
      :type="diagnosticoOperacional.tipo"
      variant="tonal"
      density="compact"
      class="mb-4"
    >
      <strong>{{ diagnosticoOperacional.titulo }}</strong>
      <div>{{ diagnosticoOperacional.mensagem }}</div>
    </v-alert>

    <template v-if="resposta">
      <v-alert
        v-for="(aviso, i) in resposta.avisos"
        :key="i"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-2"
      >
        {{ aviso }}
      </v-alert>

      <v-row class="mt-2">
        <v-col cols="12" md="4">
          <v-card class="table-card h-100">
            <v-card-title class="d-flex align-center gap-2">
              Plano analítico
              <v-chip v-if="resposta.nivelSensibilidade" size="x-small" color="teal" variant="tonal">
                {{ resposta.nivelSensibilidade }}
              </v-chip>
              <v-spacer />
              <v-chip v-if="resposta.statusFluxo" size="x-small" :color="statusColor" variant="tonal">
                {{ resposta.statusFluxo }}
              </v-chip>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <div class="mb-3">
                <div class="govbi-label">Métrica</div>
                <code class="govbi-code">{{ resposta.metrica || '—' }}</code>
              </div>
              <div v-if="resposta.dimensoes?.length" class="mb-3">
                <div class="govbi-label">Dimensões</div>
                <v-chip
                  v-for="d in resposta.dimensoes"
                  :key="d"
                  size="x-small"
                  class="mr-1 mt-1"
                  color="purple"
                  variant="tonal"
                >
                  {{ d }}
                </v-chip>
              </div>
              <div v-if="filtrosEntries.length" class="mb-3">
                <div class="govbi-label">Filtros</div>
                <div
                  v-for="[k, v] in filtrosEntries"
                  :key="k"
                  class="govbi-label mt-1"
                  style="color:inherit"
                >
                  <strong>{{ k }}:</strong> {{ v }}
                </div>
              </div>
              <div v-if="resposta.correlationId" class="mt-3">
                <div class="govbi-label">Correlation ID</div>
                <span class="govbi-label" style="color:inherit;font-family:monospace">
                  {{ resposta.correlationId?.slice(0, 12) }}…
                </span>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col v-if="exibirSql && resposta.sqlGerado" cols="12" md="8">
          <v-card class="table-card h-100">
            <v-card-title class="d-flex align-center gap-2">
              SQL Gerado
              <v-spacer />
              <v-btn size="x-small" variant="text" prepend-icon="mdi-content-copy" @click="copiarSql">
                Copiar
              </v-btn>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <pre class="govbi-sql">{{ resposta.sqlGerado }}</pre>
            </v-card-text>
          </v-card>
        </v-col>

        <v-col v-if="temResultado" cols="12">
          <v-card class="table-card">
            <v-card-title class="d-flex align-center gap-2">
              Resultado
              <v-chip size="x-small" variant="tonal">
                {{ resposta.resultado.linhas?.length || 0 }} linhas
              </v-chip>
              <v-chip v-if="resposta.mascaramentoAplicado" size="x-small" color="orange" variant="tonal">
                Mascaramento PII ativo
              </v-chip>
            </v-card-title>
            <v-divider />
            <v-data-table
              :headers="tabelaHeaders"
              :items="resposta.resultado.linhas || []"
              density="compact"
              :items-per-page="20"
              class="responsive-table-shell"
            />
          </v-card>
        </v-col>

        <v-col v-else-if="!resposta.requerAprovacao" cols="12">
          <v-alert type="info" variant="tonal" density="compact">
            Consulta processada — nenhum dado retornado pelo executor configurado.
          </v-alert>
        </v-col>

        <v-col v-if="resposta.requerAprovacao" cols="12">
          <v-alert type="warning" variant="tonal">
            Esta consulta requer aprovação. ID de aprovação:
            <strong>{{ resposta.aprovacaoId }}</strong>
          </v-alert>
        </v-col>
      </v-row>

      <v-card v-if="resposta.explicacao" class="table-card mt-4">
        <v-card-text>
          <div class="govbi-label mb-1">Fonte do plano</div>
          <span class="muted" style="font-size:0.84rem">{{ resposta.explicacao }}</span>
        </v-card-text>
      </v-card>
    </template>

    <template v-else-if="!carregando && !erro">
      <v-card class="table-card">
        <v-card-text class="text-center pa-8">
          <v-icon size="56" color="amber" class="mb-4">mdi-robot-outline</v-icon>
          <div class="text-h6 mb-2">GovBI IA pronto para análise</div>
          <div class="muted mb-4">
            Digite uma pergunta analítica acima e clique em <strong>Analisar</strong>.
          </div>
          <div class="d-flex flex-wrap gap-2 justify-center">
            <v-chip
              v-for="ex in exemplos"
              :key="ex"
              size="small"
              variant="outlined"
              class="cursor-pointer"
              @click="pergunta = ex"
            >
              {{ ex }}
            </v-chip>
          </div>
        </v-card-text>
      </v-card>
    </template>

    <v-card v-if="historicoConsultas.length" class="table-card mt-4">
      <v-card-title class="d-flex align-center flex-wrap gap-2">
        <span>Histórico analítico de consultas</span>
        <v-chip size="x-small" variant="tonal">{{ consultasFiltradas.length }} de {{ historicoConsultas.length }}</v-chip>
        <v-spacer />
        <v-chip v-if="temFiltroHistorico" size="x-small" color="blue" variant="tonal">Filtro ativo</v-chip>
        <v-spacer />
        <v-btn
          variant="outlined"
          size="small"
          prepend-icon="mdi-content-copy"
          :disabled="!consultasFiltradas.length"
          data-testid="govbi-exportar-evidencia"
          @click="copiarEvidencia"
        >
          Copiar evidência
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text>
        <div class="filter-grid mb-2">
          <v-select
            v-model="filtrosHistorico.status"
            :items="statusHistoricoOptions"
            item-title="label"
            item-value="value"
            label="Status"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistorico"
          />
          <v-select
            v-model="filtrosHistorico.fonte"
            :items="fonteHistoricoOptions"
            item-title="label"
            item-value="value"
            label="Fonte"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistorico"
          />
          <v-select
            v-model="filtrosHistorico.fallback"
            :items="fallbackHistoricoOptions"
            item-title="label"
            item-value="value"
            label="Fallback"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistorico"
          />
          <v-text-field
            v-model="filtrosHistorico.data"
            label="Data"
            type="date"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistorico"
          />
          <v-text-field
            v-model="filtrosHistorico.correlation_id"
            label="Correlation ID"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            @update:model-value="sincronizarQueryHistorico"
          />
          <v-text-field
            v-model="filtrosHistorico.busca"
            label="Busca"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            prepend-inner-icon="mdi-magnify"
            @update:model-value="sincronizarQueryHistorico"
          />
        </div>
        <div class="d-flex justify-end mb-3">
          <v-btn variant="text" size="small" prepend-icon="mdi-filter-off" :disabled="!temFiltroHistorico" @click="limparFiltrosHistorico">
            Limpar filtros
          </v-btn>
        </div>
        <div class="responsive-table-shell">
          <v-data-table
            :headers="historicoHeaders"
            :items="consultasFiltradas"
            density="compact"
            :items-per-page="10"
          >
          <template #item.consultadoEm="{ item }">
            <span class="text-caption">{{ formatarDataHistorico(item.consultadoEm) }}</span>
          </template>
          <template #item.latenciaMs="{ item }">
            <span>{{ item.latenciaMs }} ms</span>
          </template>
          <template #item.statusFluxo="{ item }">
            <v-chip size="x-small" :color="corStatusHistorico(item.statusFluxo)" variant="tonal">
              {{ item.statusFluxo }}
            </v-chip>
          </template>
          <template #item.fallback="{ item }">
            <v-chip size="x-small" :color="item.fallback ? 'orange' : 'green'" variant="tonal">
              {{ item.fallback ? 'Sim' : 'Não' }}
            </v-chip>
          </template>
          <template #item.correlationId="{ item }">
            <span
              v-if="item.correlationId"
              class="correlation-link"
              role="button"
              tabindex="0"
              @click="filtrarHistoricoPorCorrelation(item.correlationId)"
            >
              {{ item.correlationId.slice(0, 14) }}…
            </span>
            <span v-else>—</span>
          </template>
          </v-data-table>
        </div>
      </v-card-text>
    </v-card>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import { api } from '../services/api'
import {
  calcularMetricasGovbi,
  carregarHistoricoGovbi,
  criarQueryFiltrosGovbi,
  criarRegistroConsultaGovbi,
  exportarEvidenciaGovbi,
  filtrarConsultasGovbi,
  normalizarFiltrosGovbi,
  possuiFiltroAtivo,
  salvarHistoricoGovbi,
} from '../utils/filtrosGovbi'
import { executarFuncionamentoGovbi } from '../utils/govbiFuncionamento'

const route = useRoute()
const router = useRouter()

const GOVBI_TIMEOUT_MS = Number(import.meta.env.VITE_GOVBI_TIMEOUT_MS || 15000)

const govbiApi = api

const pergunta = ref('')
const exibirSql = ref(true)
const carregando = ref(false)
const erro = ref('')
const resposta = ref(null)
const diagnosticoOperacional = ref(null)
const historicoConsultas = ref([])
const filtrosHistorico = reactive(normalizarFiltrosGovbi(route.query))
const verificandoFuncionamento = ref(false)
const funcionamentoResumo = ref({
  executadoEm: '',
  total: 0,
  aprovados: 0,
  reprovados: 0,
  percentual: 0,
  completo: false,
  resultados: [],
})

const funcionamentoHeaders = [
  { title: 'Teste', key: 'nome' },
  { title: 'Categoria', key: 'categoria', width: '110px' },
  { title: 'Status', key: 'ok', width: '90px' },
  { title: 'Detalhe', key: 'detalhe' },
]

const funcionamentoExecutadoEmLabel = computed(() => {
  if (!funcionamentoResumo.value.executadoEm) return 'Aguardando primeira verificação…'
  return new Date(funcionamentoResumo.value.executadoEm).toLocaleString('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'medium',
  })
})

const statusHistoricoOptions = [
  { label: 'Concluído', value: 'CONCLUIDO' },
  { label: 'Modo degradado', value: 'MODO_DEGRADADO' },
  { label: 'Pendente aprovação', value: 'PENDENTE_APROVACAO' },
  { label: 'Erro', value: 'ERRO' },
]
const fonteHistoricoOptions = [
  { label: 'Backend', value: 'backend' },
  { label: 'Fallback', value: 'fallback' },
  { label: 'Proxy', value: 'proxy' },
]
const fallbackHistoricoOptions = [
  { label: 'Com fallback', value: 'true' },
  { label: 'Sem fallback', value: 'false' },
]
const historicoHeaders = [
  { title: 'Data', key: 'consultadoEm', width: '140px' },
  { title: 'Pergunta', key: 'pergunta' },
  { title: 'Status', key: 'statusFluxo', width: '130px' },
  { title: 'Fonte', key: 'fonte', width: '90px' },
  { title: 'Latência', key: 'latenciaMs', width: '90px' },
  { title: 'Fallback', key: 'fallback', width: '90px' },
  { title: 'Correlation ID', key: 'correlationId', width: '150px' },
]

const consultasFiltradas = computed(() => filtrarConsultasGovbi(historicoConsultas.value, filtrosHistorico))
const temFiltroHistorico = computed(() => possuiFiltroAtivo(filtrosHistorico))
const resumoMetricas = computed(() => calcularMetricasGovbi(historicoConsultas.value))

const metricasGovbi = computed(() => [
  {
    id: 'total',
    label: 'Consultas',
    value: resumoMetricas.value.total,
    semaforo: resumoMetricas.value.total > 0 ? 'verde' : 'desconhecido',
    icon: 'mdi-robot-outline',
    hint: 'Total de consultas na sessão',
    filtros: {},
  },
  {
    id: 'sucesso',
    label: 'Sucesso',
    value: resumoMetricas.value.sucesso,
    semaforo: resumoMetricas.value.sucesso > 0 ? 'verde' : 'desconhecido',
    icon: 'mdi-check-circle-outline',
    hint: 'Consultas concluídas sem fallback',
    filtros: { status: 'CONCLUIDO', fallback: 'false' },
  },
  {
    id: 'degradado',
    label: 'Degradado',
    value: resumoMetricas.value.erros,
    semaforo: resumoMetricas.value.erros > 0 ? 'vermelho' : 'verde',
    icon: 'mdi-alert-circle-outline',
    hint: 'Consultas com erro ou modo degradado',
    filtros: { status: 'MODO_DEGRADADO' },
  },
  {
    id: 'latencia',
    label: 'Latência média',
    value: resumoMetricas.value.latenciaMediaMs ? `${resumoMetricas.value.latenciaMediaMs} ms` : '—',
    semaforo: resumoMetricas.value.latenciaMediaMs > 10000 ? 'amarelo' : 'verde',
    icon: 'mdi-timer-outline',
    hint: 'Tempo médio de resposta das consultas',
    filtros: {},
  },
])

watch(
  () => route.query,
  (query) => Object.assign(filtrosHistorico, normalizarFiltrosGovbi(query)),
)

onMounted(() => {
  historicoConsultas.value = carregarHistoricoGovbi()
  executarVerificacaoFuncionamento()
})

async function executarVerificacaoFuncionamento() {
  verificandoFuncionamento.value = true
  try {
    funcionamentoResumo.value = await executarFuncionamentoGovbi(govbiApi)
  } catch (error) {
    funcionamentoResumo.value = {
      executadoEm: new Date().toISOString(),
      total: 1,
      aprovados: 0,
      reprovados: 1,
      percentual: 0,
      completo: false,
      resultados: [{
        id: 'execucao-funcionamento',
        nome: 'Execução da suíte de funcionamento',
        ok: false,
        detalhe: error?.message || 'Falha inesperada',
        categoria: 'runtime',
      }],
    }
  } finally {
    verificandoFuncionamento.value = false
  }
}

const exemplos = [
  'Quantas propostas por mês em 2024?',
  'Total por situação aprovada vs reprovada',
  'Propostas por unidade no último trimestre',
]

const filtrosEntries = computed(() => Object.entries(resposta.value?.filtros || {}))

const tabelaHeaders = computed(() =>
  (resposta.value?.resultado?.colunas || []).map((c) => ({ title: c, key: c }))
)

const temResultado = computed(
  () => (resposta.value?.resultado?.colunas?.length || 0) > 0
)

const statusColor = computed(() => {
  const s = resposta.value?.statusFluxo
  if (s === 'CONCLUIDO') return 'green'
  if (s === 'MODO_DEGRADADO') return 'orange'
  if (s === 'PENDENTE_APROVACAO') return 'amber'
  if (s === 'ERRO') return 'red'
  return 'grey'
})

async function perguntar() {
  const perguntaNormalizada = pergunta.value.trim()
  if (!perguntaNormalizada) return

  carregando.value = true
  erro.value = ''
  resposta.value = null
  diagnosticoOperacional.value = null
  const inicio = Date.now()

  try {
    const correlationId = criarCorrelationId()
    const { data } = await govbiApi.post(
      '/govbi/perguntas',
      {
        pergunta: perguntaNormalizada,
        formatoResposta: 'tabela',
        exibirSql: exibirSql.value,
      },
      {
        headers: {
          'X-Correlation-Id': correlationId,
        },
        timeout: GOVBI_TIMEOUT_MS,
      }
    )

    resposta.value = normalizarRespostaGovBI(data, perguntaNormalizada)
    diagnosticoOperacional.value = montarDiagnosticoSucesso(resposta.value)
    registrarConsultaHistorico({
      pergunta: perguntaNormalizada,
      statusFluxo: resposta.value.statusFluxo,
      fonte: resposta.value.statusFluxo === 'MODO_DEGRADADO' ? 'fallback' : 'backend',
      latenciaMs: Date.now() - inicio,
      correlationId: resposta.value.correlationId,
      fallback: resposta.value.statusFluxo === 'MODO_DEGRADADO',
      explicacao: resposta.value.explicacao,
    })
  } catch (e) {
    const detalhe = extrairDetalheErro(e)
    resposta.value = null
    diagnosticoOperacional.value = {
      tipo: 'error',
      titulo: 'Falha de transporte com o backend ReqSys',
      mensagem: `O proxy GovBI não respondeu. Verifique conectividade com /govbi/perguntas. Detalhe: ${detalhe}`,
    }
    erro.value = detalhe
    registrarConsultaHistorico({
      pergunta: perguntaNormalizada,
      statusFluxo: 'ERRO',
      fonte: 'transporte',
      latenciaMs: Date.now() - inicio,
      correlationId: criarCorrelationId(),
      fallback: false,
      erro: detalhe,
      explicacao: 'Erro de transporte — backend indisponível; modo degradado GovBI não aplicável sem resposta HTTP.',
    })
  } finally {
    carregando.value = false
  }
}

function registrarConsultaHistorico(dados) {
  const registro = criarRegistroConsultaGovbi(dados)
  historicoConsultas.value = [registro, ...historicoConsultas.value].slice(0, 50)
  salvarHistoricoGovbi(historicoConsultas.value)
}

function sincronizarQueryHistorico() {
  router.replace({ path: route.path, query: criarQueryFiltrosGovbi(filtrosHistorico) })
}

function limparFiltrosHistorico() {
  Object.assign(filtrosHistorico, { status: '', fonte: '', correlation_id: '', data: '', busca: '', fallback: '' })
  sincronizarQueryHistorico()
}

function aplicarFiltroMetrica(novosFiltros = {}) {
  Object.assign(filtrosHistorico, normalizarFiltrosGovbi(novosFiltros))
  sincronizarQueryHistorico()
}

function copiarEvidencia() {
  const texto = exportarEvidenciaGovbi(historicoConsultas.value, filtrosHistorico)
  navigator.clipboard.writeText(texto).catch(() => {})
}

function filtrarHistoricoPorCorrelation(correlationId) {
  filtrosHistorico.correlation_id = correlationId
  sincronizarQueryHistorico()
}

function formatarDataHistorico(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function corStatusHistorico(status) {
  if (status === 'CONCLUIDO') return 'green'
  if (status === 'MODO_DEGRADADO') return 'orange'
  if (status === 'ERRO') return 'red'
  return 'grey'
}

function montarDiagnosticoSucesso(respostaNormalizada) {
  if (respostaNormalizada.statusFluxo === 'ERRO') {
    return {
      tipo: 'error',
      titulo: 'Consulta GovBI rejeitada',
      mensagem: respostaNormalizada.avisos?.[0] || 'O serviço GovBI externo rejeitou a consulta.',
    }
  }

  if (respostaNormalizada.statusFluxo === 'MODO_DEGRADADO') {
    return {
      tipo: 'warning',
      titulo: 'GovBI IA em modo degradado governado',
      mensagem: 'O backend ReqSys respondeu, mas o serviço GovBI externo ficou indisponível ou fora do contrato.',
    }
  }

  return {
    tipo: 'success',
    titulo: 'Consulta GovBI processada',
    mensagem: 'O backend ReqSys processou a consulta GovBI dentro do contrato esperado.',
  }
}

function normalizarRespostaGovBI(data, perguntaOriginal) {
  const resultado = data?.resultado || {}
  const colunas = Array.isArray(resultado.colunas) ? resultado.colunas : []
  const linhas = Array.isArray(resultado.linhas) ? resultado.linhas : []

  return {
    avisos: Array.isArray(data?.avisos) ? data.avisos : [],
    nivelSensibilidade: data?.nivelSensibilidade || 'BAIXA',
    statusFluxo: data?.statusFluxo || 'CONCLUIDO',
    metrica: data?.metrica || inferirMetrica(perguntaOriginal),
    dimensoes: Array.isArray(data?.dimensoes) ? data.dimensoes : inferirDimensoes(perguntaOriginal),
    filtros: data?.filtros && typeof data.filtros === 'object' ? data.filtros : {},
    correlationId: data?.correlationId || criarCorrelationId(),
    sqlGerado: data?.sqlGerado || '',
    resultado: { colunas, linhas },
    mascaramentoAplicado: Boolean(data?.mascaramentoAplicado),
    requerAprovacao: Boolean(data?.requerAprovacao),
    aprovacaoId: data?.aprovacaoId || null,
    explicacao: data?.explicacao || 'Resposta normalizada pelo ReqSys para manter contrato estável da UI.',
  }
}

function extrairDetalheErro(e) {
  const status = e.response?.status
  const statusText = e.response?.statusText
  const data = e.response?.data
  const mensagemServidor = data?.message || data?.error || data?.detail
  const mensagem = mensagemServidor || e.message || 'erro desconhecido'

  if (status) return `HTTP ${status}${statusText ? ` ${statusText}` : ''} - ${mensagem}`
  if (e.code === 'ECONNABORTED') return `timeout após ${GOVBI_TIMEOUT_MS}ms`
  if (e.request) return `sem resposta do backend - ${mensagem}`
  return mensagem
}

function inferirMetrica(texto) {
  const t = texto.toLowerCase()
  if (t.includes('quant') || t.includes('total')) return 'contagem_registros'
  if (t.includes('média') || t.includes('media')) return 'media'
  if (t.includes('percent') || t.includes('%')) return 'percentual'
  return 'analise_exploratoria'
}

function inferirDimensoes(texto) {
  const t = texto.toLowerCase()
  const dimensoes = []
  if (t.includes('mês') || t.includes('mes') || t.includes('mensal')) dimensoes.push('mes')
  if (t.includes('unidade')) dimensoes.push('unidade')
  if (t.includes('situação') || t.includes('situacao') || t.includes('status')) dimensoes.push('situacao')
  if (t.includes('trimestre')) dimensoes.push('trimestre')
  return dimensoes.length ? dimensoes : ['periodo']
}

function criarCorrelationId() {
  if (crypto?.randomUUID) return crypto.randomUUID()
  return `govbi-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function limpar() {
  pergunta.value = ''
  resposta.value = null
  erro.value = ''
  diagnosticoOperacional.value = null
}

function copiarSql() {
  if (resposta.value?.sqlGerado) {
    navigator.clipboard.writeText(resposta.value.sqlGerado).catch(() => {})
  }
}
</script>

<style scoped>
.govbi-label {
  font-size: 0.78rem;
  color: var(--muted, #888);
  margin-bottom: 2px;
}
.govbi-code {
  font-family: monospace;
  font-size: 0.88rem;
}
.govbi-sql {
  background: rgba(0, 0, 0, 0.12);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 0.82rem;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: monospace;
}
.cursor-pointer {
  cursor: pointer;
}
.correlation-link {
  color: rgb(var(--v-theme-primary));
  cursor: pointer;
  text-decoration: underline dotted;
  font-family: monospace;
  font-size: 0.78rem;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
</style>
