<template>
  <main class="monitoramento-operacional" aria-labelledby="titulo-monitoramento">
    <section class="cabecalho">
      <div>
        <p class="eyebrow">ReqSys Operacional</p>
        <h1 id="titulo-monitoramento">Monitoramento Operacional</h1>
        <p>
          Visão mínima para acompanhar PRs, CI/CD, gates, integrações e pendências críticas com rastreabilidade.
        </p>
      </div>
      <button type="button" @click="carregarMonitoramento">Atualizar</button>
    </section>

    <section class="cards" aria-label="Indicadores operacionais">
      <article class="card">
        <span>Estado geral</span>
        <strong>{{ resumo.estado_geral || 'desconhecido' }}</strong>
      </article>
      <article class="card">
        <span>Bloqueios</span>
        <strong>{{ resumo.bloqueios ?? 0 }}</strong>
      </article>
      <article class="card">
        <span>Pendências</span>
        <strong>{{ resumo.pendencias ?? 0 }}</strong>
      </article>
      <article class="card">
        <span>Itens</span>
        <strong>{{ resumo.total_itens ?? itens.length }}</strong>
      </article>
    </section>

    <section class="filtros" aria-label="Filtros do analítico">
      <label>
        Estado
        <select v-model="filtroEstado">
          <option value="">Todos</option>
          <option value="verde">Verde</option>
          <option value="amarelo">Amarelo</option>
          <option value="vermelho">Vermelho</option>
          <option value="bloqueado">Bloqueado</option>
          <option value="desconhecido">Desconhecido</option>
        </select>
      </label>
      <label>
        Severidade
        <select v-model="filtroSeveridade">
          <option value="">Todas</option>
          <option value="baixa">Baixa</option>
          <option value="media">Média</option>
          <option value="alta">Alta</option>
          <option value="critica">Crítica</option>
        </select>
      </label>
    </section>

    <section class="analitico" aria-label="Itens monitorados">
      <table>
        <thead>
          <tr>
            <th>Tipo</th>
            <th>Referência</th>
            <th>Título</th>
            <th>Estado</th>
            <th>Severidade</th>
            <th>Origem</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in itensFiltrados" :key="`${item.tipo}-${item.referencia}`">
            <td>{{ item.tipo }}</td>
            <td>{{ item.referencia }}</td>
            <td>{{ item.titulo }}</td>
            <td>{{ item.estado }}</td>
            <td>{{ item.severidade }}</td>
            <td>{{ item.origem }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const resumo = ref({})
const itens = ref([])
const filtroEstado = ref(route.query.estado || '')
const filtroSeveridade = ref(route.query.severidade || '')

const itensFiltrados = computed(() => itens.value.filter((item) => {
  const estadoOk = !filtroEstado.value || item.estado === filtroEstado.value
  const severidadeOk = !filtroSeveridade.value || item.severidade === filtroSeveridade.value
  return estadoOk && severidadeOk
}))

async function carregarMonitoramento() {
  const resposta = await fetch('/monitoramento-operacional', {
    headers: {
      Accept: 'application/json',
      'X-Correlation-Id': `frontend-monitoramento-${Date.now()}`,
    },
  })
  if (!resposta.ok) {
    throw new Error('Falha ao carregar monitoramento operacional')
  }
  const payload = await resposta.json()
  resumo.value = payload.data?.resumo || {}
  itens.value = payload.data?.itens || []
}

watch([filtroEstado, filtroSeveridade], () => {
  router.replace({
    query: {
      ...route.query,
      estado: filtroEstado.value || undefined,
      severidade: filtroSeveridade.value || undefined,
    },
  })
})

onMounted(carregarMonitoramento)
</script>

<style scoped>
.monitoramento-operacional {
  display: grid;
  gap: 1rem;
  padding: 1rem;
}

.cabecalho,
.filtros,
.cards {
  display: grid;
  gap: 1rem;
}

.cabecalho {
  align-items: center;
}

.eyebrow {
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.cards {
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

.card {
  border: 1px solid #d0d7de;
  border-radius: 12px;
  padding: 1rem;
}

.card span,
.card strong {
  display: block;
}

.card strong {
  font-size: 1.5rem;
  margin-top: 0.5rem;
}

.filtros {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.filtros label {
  display: grid;
  gap: 0.25rem;
}

.analitico {
  overflow-x: auto;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th,
td {
  border-bottom: 1px solid #d0d7de;
  padding: 0.75rem;
  text-align: left;
}

@media (min-width: 768px) {
  .cabecalho {
    grid-template-columns: 1fr auto;
  }
}
</style>
