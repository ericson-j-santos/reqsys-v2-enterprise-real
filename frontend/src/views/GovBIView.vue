<template>
  <section class="page">
    <PageHeader
      title="GovBI IA"
      subtitle="Consultas analíticas em linguagem natural com BI governado por inteligência artificial."
      chip="Beta"
      chip-color="blue"
      chip-tooltip="Integração com GovBI IA com fallback governado para indisponibilidade externa"
    >
      <template #actions>
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

    <!-- Input de pergunta -->
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

    <!-- Erro -->
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

    <!-- Resultado -->
    <template v-if="resposta">
      <!-- Avisos de governança -->
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
        <!-- Plano analítico -->
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

        <!-- SQL gerado -->
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

        <!-- Resultado da consulta -->
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
            />
          </v-card>
        </v-col>

        <!-- Sem resultado -->
        <v-col v-else-if="!resposta.requerAprovacao" cols="12">
          <v-alert type="info" variant="tonal" density="compact">
            Consulta processada — nenhum dado retornado pelo executor configurado.
          </v-alert>
        </v-col>

        <!-- Requer aprovação -->
        <v-col v-if="resposta.requerAprovacao" cols="12">
          <v-alert type="warning" variant="tonal">
            Esta consulta requer aprovação. ID de aprovação:
            <strong>{{ resposta.aprovacaoId }}</strong>
          </v-alert>
        </v-col>
      </v-row>

      <!-- Explicação -->
      <v-card v-if="resposta.explicacao" class="table-card mt-4">
        <v-card-text>
          <div class="govbi-label mb-1">Fonte do plano</div>
          <span class="muted" style="font-size:0.84rem">{{ resposta.explicacao }}</span>
        </v-card-text>
      </v-card>
    </template>

    <!-- Estado inicial (sem resposta) -->
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
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import axios from 'axios'
import PageHeader from '../components/PageHeader.vue'

const GOVBI_URL = import.meta.env.VITE_GOVBI_URL || 'https://govbi-ia-hom.fly.dev'
const GOVBI_TIMEOUT_MS = Number(import.meta.env.VITE_GOVBI_TIMEOUT_MS || 15000)

const govbiApi = axios.create({
  baseURL: GOVBI_URL,
  timeout: GOVBI_TIMEOUT_MS,
})

const pergunta = ref('')
const exibirSql = ref(true)
const carregando = ref(false)
const erro = ref('')
const resposta = ref(null)
const diagnosticoOperacional = ref(null)

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

  try {
    const { data } = await govbiApi.post(
      '/api/v1/perguntas',
      {
        pergunta: perguntaNormalizada,
        formatoResposta: 'tabela',
        exibirSql: exibirSql.value,
      },
      {
        headers: {
          'X-Usuario': 'reqsys-usuario',
          'X-Perfil': 'ANALISTA',
          'X-Escopo-Unidade': 'GERAL',
        },
      }
    )

    resposta.value = normalizarRespostaGovBI(data, perguntaNormalizada)
    diagnosticoOperacional.value = {
      tipo: 'success',
      titulo: 'Consulta GovBI processada',
      mensagem: 'O serviço GovBI IA respondeu dentro do contrato esperado.',
    }
  } catch (e) {
    const detalhe = extrairDetalheErro(e)
    resposta.value = gerarRespostaFallback(perguntaNormalizada, detalhe)
    diagnosticoOperacional.value = {
      tipo: 'warning',
      titulo: 'GovBI IA em modo degradado',
      mensagem: `O serviço externo não respondeu corretamente. A tela exibiu um plano governado local para manter a operação assistida. Detalhe: ${detalhe}`,
    }
  } finally {
    carregando.value = false
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

function gerarRespostaFallback(perguntaOriginal, detalheErro) {
  const metrica = inferirMetrica(perguntaOriginal)
  const dimensoes = inferirDimensoes(perguntaOriginal)
  const correlationId = criarCorrelationId()

  return {
    avisos: [
      'GovBI IA externo indisponível ou fora do contrato esperado.',
      'Resultado abaixo é um plano analítico governado local, sem execução contra base real.',
      'Use o Correlation ID para rastrear a ocorrência e validar o serviço GovBI/Fly.',
    ],
    nivelSensibilidade: 'BAIXA',
    statusFluxo: 'MODO_DEGRADADO',
    metrica,
    dimensoes,
    filtros: inferirFiltros(perguntaOriginal),
    correlationId,
    sqlGerado: montarSqlSeguro(metrica, dimensoes),
    resultado: {
      colunas: ['item', 'valor', 'status'],
      linhas: [
        {
          item: 'Pergunta recebida',
          valor: perguntaOriginal,
          status: 'VALIDADA_LOCALMENTE',
        },
        {
          item: 'Serviço GovBI',
          valor: detalheErro,
          status: 'INDISPONIVEL_OU_FORA_DO_CONTRATO',
        },
        {
          item: 'Próxima ação',
          valor: 'Validar endpoint /api/v1/perguntas, CORS, timeout e contrato de resposta.',
          status: 'ACAO_OPERACIONAL',
        },
      ],
    },
    mascaramentoAplicado: true,
    requerAprovacao: false,
    aprovacaoId: null,
    explicacao: 'Fallback governado gerado no front para impedir falha bloqueante na consulta inteligente.',
  }
}

function extrairDetalheErro(e) {
  const status = e.response?.status
  const statusText = e.response?.statusText
  const data = e.response?.data
  const mensagemServidor = data?.message || data?.error || data?.detail
  const mensagem = mensagemServidor || e.message || 'erro desconhecido'

  if (status) return `HTTP ${status}${statusText ? ` ${statusText}` : ''} - ${mensagem}`
  if (e.code === 'ECONNABORTED') return `timeout após ${GOVBI_TIMEOUT_MS}ms em ${GOVBI_URL}`
  if (e.request) return `sem resposta de ${GOVBI_URL} - ${mensagem}`
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

function inferirFiltros(texto) {
  const filtros = {}
  const ano = texto.match(/20\d{2}/)?.[0]
  if (ano) filtros.ano = ano
  if (texto.toLowerCase().includes('último trimestre') || texto.toLowerCase().includes('ultimo trimestre')) {
    filtros.periodo_relativo = 'ultimo_trimestre'
  }
  return filtros
}

function montarSqlSeguro(metrica, dimensoes) {
  const dimensaoSelect = dimensoes.join(', ') || 'periodo'
  return `-- SQL ilustrativo governado; não executado contra base real\nSELECT ${dimensaoSelect}, COUNT(*) AS ${metrica}\nFROM fonte_governada\nWHERE 1 = 1\nGROUP BY ${dimensaoSelect};`
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
</style>
