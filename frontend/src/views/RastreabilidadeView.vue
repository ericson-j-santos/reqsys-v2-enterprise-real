<template>
  <section class="page" data-testid="route-rastreabilidade">
    <div class="page-header">
      <div>
        <h1>Matriz de Rastreabilidade</h1>
        <p class="muted trace-subtitle">
          Vínculo entre requisito, work item agile e entrega Git detectada por webhooks ou registro manual.
        </p>
      </div>
      <div class="header-actions">
        <button type="button" :disabled="carregando" @click="carregarMatriz">
          {{ carregando ? 'Atualizando...' : 'Atualizar' }}
        </button>
      </div>
    </div>

    <p v-if="erro" class="alerta erro" role="alert">{{ erro }}</p>

    <v-alert type="info" variant="tonal" class="mb-4">
      Dados carregados de <code>/v1/rastreabilidade/matriz</code>. Redmine e Planner entram em fase posterior.
    </v-alert>

    <v-card class="table-card">
      <v-card-title class="py-3 px-4">
        Encadeamento de artefatos
        <span v-if="total" class="muted text-caption">({{ total }} registros)</span>
      </v-card-title>
      <v-divider />
      <p v-if="!linhas.length && !carregando" class="pa-4 muted">Nenhum vínculo Git registrado ainda.</p>
      <v-table v-else>
        <thead>
          <tr>
            <th>Requisito</th>
            <th>História</th>
            <th>Redmine</th>
            <th>Planner</th>
            <th>Entrega</th>
            <th>Ambiente</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, idx) in linhas" :key="`${r.requisito}-${r.entrega}-${idx}`">
            <td>
              <strong>{{ r.requisito }}</strong>
              <div class="muted text-caption">{{ r.repositorio }}</div>
            </td>
            <td>
              <router-link v-if="r.work_item_id" :to="`/agile-runtime`" class="link-interno">
                {{ r.historia }}
              </router-link>
              <span v-else>{{ r.historia }}</span>
            </td>
            <td>{{ r.redmine }}</td>
            <td>{{ r.planner }}</td>
            <td>
              <a
                v-if="r.entrega_url"
                :href="r.entrega_url"
                target="_blank"
                rel="noopener noreferrer"
              >{{ r.entrega }}</a>
              <a
                v-else-if="r.change_url"
                :href="r.change_url"
                target="_blank"
                rel="noopener noreferrer"
              >PR vinculado</a>
              <code v-else>{{ r.entrega }}</code>
            </td>
            <td>{{ r.ambiente }}</td>
            <td>
              <v-chip size="small" :color="r.status === 'rastreado' ? 'green' : 'amber'">{{ r.status }}</v-chip>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const linhas = ref([])
const total = ref(0)
const carregando = ref(false)
const erro = ref('')

async function carregarMatriz() {
  carregando.value = true
  erro.value = ''
  try {
    const { data } = await api.get('/v1/rastreabilidade/matriz', { params: { limit: 100 } })
    const payload = data.data ?? data
    linhas.value = payload.linhas ?? []
    total.value = payload.total ?? linhas.value.length
  } catch (error) {
    erro.value = error.response?.data?.detail || 'Erro ao carregar matriz de rastreabilidade.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregarMatriz)
</script>

<style scoped>
.trace-subtitle {
  max-width: 58ch;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.alerta.erro {
  color: #b00020;
}

.link-interno {
  color: inherit;
}
</style>
