<template>
  <section class="dashboard-operacional" data-testid="route-dashboard" aria-labelledby="titulo-dashboard">
    <div class="dashboard-header">
      <div>
        <p class="figma-eyebrow">ReqSys · Uso real · Painel do dia</p>
        <h1 id="titulo-dashboard">Painel do dia</h1>
        <p class="muted dashboard-subtitle">
          Foque no que precisa de decisão: novas demandas, requisitos com baixa qualidade, aprovações, rastreabilidade e próximos passos.
        </p>
      </div>
      <div class="header-actions">
        <AmbienteNavigator :environment-hint="ambienteLabel" test-id="ambiente-chip" />
        <div
          class="figma-semaforo-geral"
          :class="`figma-semaforo-geral--${semaforoGeralValor}`"
          data-testid="dashboard-semaforo-geral"
        >
          <span class="figma-semaforo-dot" :class="`figma-semaforo-dot--${semaforoGeralValor}`" />
          Prontidão: {{ semaforoGeralLabel }}
        </div>
        <v-btn
          color="primary"
          variant="flat"
          class="figma-btn-atualizar"
          :loading="carregando"
          data-testid="dashboard-atualizar"
          @click="carregarTudo"
        >
          Atualizar
        </v-btn>
      </div>
    </div>

    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <section class="jornada-card figma-panel" aria-labelledby="titulo-jornada-real">
      <div>
        <h2 id="titulo-jornada-real">Jornada principal do requisito</h2>
        <p class="panel-lead">
          Entrada → Refinamento com IA → Critérios de aceite → Aprovação → Rastreabilidade → Publicação.
        </p>
      </div>
      <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus-circle-outline" data-testid="dashboard-novo-requisito" @click="irPara({ path: '/requisitos', query: { acao: 'novo' } })">
        Novo requisito
      </v-btn>
    </section>

    <div class="metrics-grid">
      <OperationalMetricCard
        v-for="card in cards"
        :key="card.id"
        :label="card.label"
        :value="card.value"
        :semaforo="card.semaforo"
        :icon="card.icon"
        :hint="card.hint"
        :test-id="`metric-card-${card.id}`"
        @drilldown="irPara(card.rota)"
      />
    </div>

    <div class="lower-panels">
      <section class="figma-panel pipeline-panel">
        <h2>Próximas ações</h2>
        <p class="panel-lead">Etapas orientadas à rotina do analista, sem exigir leitura de detalhes técnicos de ambiente, CI ou runtime.</p>
        <div class="timeline-steps">
          <div
            v-for="step in pipelineSteps"
            :key="step.id"
            class="timeline-step"
            role="button"
            tabindex="0"
            :data-testid="`pipeline-step-${step.id}`"
            @click="irPara(step.rota)"
            @keyup.enter="irPara(step.rota)"
            @keyup.space.prevent="irPara(step.rota)"
          >
            <div>
              <strong>{{ step.titulo }}</strong>
              <span>{{ step.descricao }}</span>
            </div>
            <span class="step-btn">Abrir</span>
          </div>
        </div>
      </section>

      <section class="figma-panel info-panel" data-testid="dashboard-info-card">
        <h2>Atalhos de decisão</h2>
        <p class="panel-lead">Acessos úteis para transformar demanda em requisito pronto para desenvolvimento.</p>
        <div class="figma-list">
          <div
            v-for="item in painelDireito"
            :key="item.id"
            class="figma-list-item"
            role="button"
            tabindex="0"
            :data-testid="item.testId"
            @click="irPara(item.rota)"
            @keyup.enter="irPara(item.rota)"
            @keyup.space.prevent="irPara(item.rota)"
          >
            <strong>{{ item.title }}</strong>
            <small>{{ item.subtitle }}</small>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import OperationalMetricCard from '../components/OperationalMetricCard.vue'
import AmbienteNavigator from '../components/AmbienteNavigator.vue'
import { useRequisitosStore } from '../stores/requisitos'
import { semaforoGeral, normalizarSemaforo } from '../utils/filtrosMonitoramento'

const store = useRequisitosStore()
const router = useRouter()
const carregando = ref(false)
const erro = ref('')

onMounted(carregarTudo)

async function carregarTudo() {
  carregando.value = true
  erro.value = ''
  try {
    await Promise.all([
      store.carregarMetricas(),
      store.carregarDashboardInfo(),
      store.carregarQualidadeIA(),
    ])
  } catch (e) {
    erro.value = e?.message || 'Erro ao carregar o painel do dia'
  } finally {
    carregando.value = false
  }
}

function semaforoQualidadeIA(score) {
  const valor = Number(score ?? 0)
  if (valor < 70) return 'vermelho'
  if (valor < 90) return 'amarelo'
  return 'verde'
}

function semaforoContagem(valor, limiarAtencao = 0) {
  return Number(valor) > limiarAtencao ? 'amarelo' : 'verde'
}

function semaforoProntidao(valor, limiarBloqueio = 0) {
  return Number(valor) > limiarBloqueio ? 'vermelho' : 'verde'
}

const cards = computed(() => {
  const scoreIA = Math.round(store.qualidadeIAResumo.score_geral ?? 0)
  const pendentes = store.metricas.pendentes ?? 0
  const emAnalise = store.metricas.em_analise ?? 0
  const aprovados = store.metricas.aprovados ?? 0
  const total = store.metricas.total ?? 0
  const baixaQualidade = scoreIA < 70 ? emAnalise || pendentes || 1 : 0

  return [
    {
      id: 'minhas-demandas',
      label: 'Demandas abertas',
      value: total,
      semaforo: 'verde',
      icon: 'mdi-file-document-edit-outline',
      hint: 'Demandas e requisitos cadastrados para acompanhamento',
      rota: { path: '/requisitos' },
    },
    {
      id: 'aguardando-refinamento',
      label: 'Em refinamento',
      value: emAnalise,
      semaforo: semaforoContagem(emAnalise),
      icon: 'mdi-clipboard-text-search-outline',
      hint: 'Itens que precisam virar requisito testável, história ou critério de aceite',
      rota: { path: '/requisitos', query: { status: 'em_analise' } },
    },
    {
      id: 'baixa-qualidade',
      label: 'Baixa qualidade',
      value: baixaQualidade,
      semaforo: semaforoProntidao(baixaQualidade),
      icon: 'mdi-alert-decagram-outline',
      hint: 'Itens que exigem revisão por clareza, completude ou testabilidade',
      rota: { path: '/qualidade-ia' },
    },
    {
      id: 'aprovados',
      label: 'Aprovados',
      value: aprovados,
      semaforo: 'verde',
      icon: 'mdi-check-decagram-outline',
      hint: 'Requisitos prontos para execução ou publicação',
      rota: { path: '/requisitos', query: { status: 'aprovado' } },
    },
    {
      id: 'rastreabilidade',
      label: 'Rastreabilidade',
      value: aprovados,
      semaforo: aprovados > 0 ? 'verde' : 'amarelo',
      icon: 'mdi-vector-link',
      hint: 'Itens que devem manter origem, decisão, história, entrega e evidência',
      rota: { path: '/rastreabilidade' },
    },
    {
      id: 'pendencias',
      label: 'Pendências',
      value: pendentes,
      semaforo: semaforoContagem(pendentes),
      icon: 'mdi-alert-circle-outline',
      hint: 'Itens aguardando triagem, decisão ou complementação',
      rota: { path: '/requisitos', query: { status: 'recebido' } },
    },
  ]
})

const resumoSemaforo = computed(() => {
  return cards.value.reduce((acc, card) => {
    const chave = card.semaforo || 'desconhecido'
    acc[chave] = (acc[chave] || 0) + 1
    return acc
  }, { verde: 0, amarelo: 0, vermelho: 0, bloqueado: 0 })
})

const semaforoGeralValor = computed(() => semaforoGeral(resumoSemaforo.value))
const semaforoGeralLabel = computed(() => normalizarSemaforo(semaforoGeralValor.value).label)

const pipelineSteps = [
  {
    id: 'entrada',
    titulo: 'Registrar ou revisar entrada',
    descricao: 'Capturar demanda, objetivo, área, urgência e impacto esperado.',
    rota: { path: '/requisitos', query: { acao: 'novo' } },
  },
  {
    id: 'refinamento',
    titulo: 'Refinar para requisito testável',
    descricao: 'Melhorar clareza, remover ambiguidade e gerar critérios de aceite.',
    rota: { path: '/qualidade-ia' },
  },
  {
    id: 'aprovacao',
    titulo: 'Aprovar ou devolver',
    descricao: 'Decidir se o item está pronto para execução ou precisa de complemento.',
    rota: { path: '/pipeline' },
  },
  {
    id: 'rastreio',
    titulo: 'Rastrear entrega',
    descricao: 'Conectar requisito, história, PR, evidência e publicação.',
    rota: { path: '/rastreabilidade' },
  },
]

const painelDireito = computed(() => [
  {
    id: 'novo-requisito',
    title: 'Cadastrar nova demanda',
    subtitle: 'Comece pela necessidade de negócio e impacto esperado',
    rota: { path: '/requisitos', query: { acao: 'novo' } },
    testId: 'destino-novo-requisito',
  },
  {
    id: 'criterios-aceite',
    title: 'Validar critérios de aceite',
    subtitle: 'Revise BDD, DoD, ambiguidade e completude',
    rota: { path: '/qualidade-ia' },
    testId: 'destino-criterios-aceite',
  },
  {
    id: 'publicar-integracao',
    title: 'Publicar em ferramenta de entrega',
    subtitle: 'Preparar envio para Planner, Redmine, GitHub ou workflow corporativo',
    rota: { path: '/painel-integracao' },
    testId: 'destino-publicar-integracao',
  },
  {
    id: 'auditar-decisao',
    title: 'Auditar decisão',
    subtitle: 'Ver linha do tempo, responsável e evidência da mudança',
    rota: { path: '/auditoria' },
    testId: 'destino-auditar-decisao',
  },
])

function irPara(rota) {
  if (!rota?.path) return
  router.push(rota)
}

const dashboardInfo = computed(() => store.dashboardInfo || {})
const resumo = computed(() => dashboardInfo.value.resumo || {})
const ambienteLabel = computed(() => (resumo.value.ambiente || 'desenvolvimento').replace(/_/g, ' '))
</script>

<style scoped>
.dashboard-operacional {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px;
}

.dashboard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.dashboard-subtitle {
  max-width: 72ch;
  margin-top: 8px;
  font-size: 14px;
}

.jornada-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 18px;
}

.jornada-card h2 {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 800;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-top: 18px;
}

.lower-panels {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 16px;
  margin-top: 18px;
}

.pipeline-panel h2,
.info-panel h2 {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 700;
}

.panel-lead {
  margin: 0 0 14px;
  color: var(--muted);
  font-size: 13px;
}

.timeline-steps {
  display: grid;
  gap: 12px;
}

.timeline-step {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}

.timeline-step:hover,
.timeline-step:focus-visible {
  background: rgba(243, 146, 0, 0.08);
  outline: none;
}

.timeline-step strong {
  display: block;
}

.timeline-step span {
  color: var(--muted);
  font-size: 13px;
}

.step-btn {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.figma-list {
  display: grid;
  gap: 8px;
}

.figma-btn-atualizar {
  border-radius: 999px !important;
  font-weight: 700 !important;
  padding-inline: 14px !important;
}

.erro {
  border: 1px solid var(--red);
  border-radius: 8px;
  color: var(--red);
  padding: 0.75rem;
}

@media (max-width: 1100px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .lower-panels {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .dashboard-header,
  .jornada-card {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    width: 100%;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .figma-pill,
  .figma-btn-atualizar {
    width: 100%;
    text-align: center;
  }
}
</style>
