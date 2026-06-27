<template>
  <section class="page agile-runtime-page" data-testid="route-agile-runtime">
    <header class="cabecalho">
      <div>
        <p class="eyebrow">ReqSys · Agile Runtime</p>
        <h1>GitHub Launchpad</h1>
        <p>Abra work items no GitHub com branch e ambiente corretos, sem sair do ReqSys.</p>
      </div>
      <button type="button" :disabled="carregando" @click="carregarWorkItems">
        {{ carregando ? 'Atualizando...' : 'Atualizar' }}
      </button>
    </header>

    <p v-if="erro" class="alerta erro" role="alert">{{ erro }}</p>

    <section class="layout" aria-label="Work items e launchpad GitHub">
      <article class="painel lista">
        <h2>Work items</h2>
        <p v-if="!workItems.length && !carregando" class="vazio">Nenhum work item cadastrado.</p>
        <ul v-else class="itens">
          <li v-for="item in workItems" :key="item.id">
            <button
              type="button"
              class="item-btn"
              :class="{ ativo: selecionado?.id === item.id }"
              @click="selecionarItem(item)"
            >
              <strong>{{ item.codigo }}</strong>
              <span>{{ item.titulo }}</span>
              <small>{{ item.status }} · {{ item.branch || 'branch pendente' }}</small>
            </button>
          </li>
        </ul>
      </article>

      <article v-if="selecionado" class="painel launchpad">
        <h2>{{ selecionado.codigo }}</h2>
        <p>{{ selecionado.titulo }}</p>

        <div class="ambientes" role="tablist" aria-label="Ambiente alvo">
          <button
            v-for="amb in ambientes"
            :key="amb.valor"
            type="button"
            role="tab"
            :aria-selected="ambiente === amb.valor"
            :class="{ ativo: ambiente === amb.valor }"
            @click="trocarAmbiente(amb.valor)"
          >
            {{ amb.rotulo }}
          </button>
        </div>

        <p v-if="carregandoLaunchpad" class="status">Carregando launchpad...</p>
        <template v-else-if="launchpad">
          <dl class="meta">
            <div><dt>Branch</dt><dd><code>{{ launchpad.branch_trabalho }}</code></dd></div>
            <div><dt>Base</dt><dd><code>{{ launchpad.branch_base }}</code></dd></div>
            <div><dt>Repositório</dt><dd><code>{{ launchpad.repositorio }}</code></dd></div>
            <div v-if="launchpad.requisito_codigo"><dt>Requisito</dt><dd>{{ launchpad.requisito_codigo }}</dd></div>
          </dl>

          <div class="acoes">
            <a
              v-if="pode('abrir_branch')"
              class="acao"
              :href="launchpad.links.branch"
              target="_blank"
              rel="noopener noreferrer"
            >Abrir branch</a>
            <a
              v-if="pode('criar_branch_github')"
              class="acao"
              :href="launchpad.links.criar_branch"
              target="_blank"
              rel="noopener noreferrer"
            >Criar branch</a>
            <a
              v-if="pode('abrir_pr')"
              class="acao"
              :href="launchpad.links.novo_pr"
              target="_blank"
              rel="noopener noreferrer"
            >Abrir PR</a>
            <a
              v-if="pode('ver_actions')"
              class="acao"
              :href="launchpad.links.actions"
              target="_blank"
              rel="noopener noreferrer"
            >Ver CI</a>
            <a
              v-if="pode('abrir_app') && launchpad.links.app_ambiente"
              class="acao"
              :href="launchpad.links.app_ambiente"
              target="_blank"
              rel="noopener noreferrer"
            >Abrir app</a>
            <a
              v-if="launchpad.links.change_request"
              class="acao secundaria"
              :href="launchpad.links.change_request"
              target="_blank"
              rel="noopener noreferrer"
            >PR vinculado</a>
            <button
              v-if="pode('criar_branch_api')"
              type="button"
              class="acao botao"
              :disabled="criandoBranch"
              @click="criarBranchApi"
            >{{ criandoBranch ? 'Criando...' : 'Criar branch (API)' }}</button>
          </div>

          <form class="trace-form" @submit.prevent="salvarRastreabilidade">
            <label>
              URL do PR (change_url)
              <input v-model="changeUrl" type="url" placeholder="https://github.com/org/repo/pull/123" />
            </label>
            <button type="submit" :disabled="salvandoTrace">Salvar rastreabilidade</button>
          </form>

          <p v-if="mensagem" class="nota sucesso" role="status">{{ mensagem }}</p>
          <p v-if="launchpad.increment_gate && !launchpad.increment_gate.permitido" class="nota alerta-gate">
            Increment gate: {{ launchpad.increment_gate.detalhe }}
          </p>
          <p v-if="launchpad.branch_existe === true" class="nota">Branch já existe no repositório.</p>
          <p v-if="launchpad.somente_leitura" class="nota">Ambiente produtivo: somente leitura.</p>
          <p class="nota mono">{{ launchpad.mensagem_commit_sugerida }}</p>
        </template>
      </article>

      <article v-else class="painel vazio-detalhe">
        <p>Selecione um work item para abrir o launchpad GitHub.</p>
      </article>
    </section>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../services/api'

const ambientes = [
  { valor: 'dev', rotulo: 'Dev' },
  { valor: 'homolog', rotulo: 'Homolog' },
  { valor: 'prod', rotulo: 'Prod' },
]

const workItems = ref([])
const selecionado = ref(null)
const launchpad = ref(null)
const ambiente = ref('dev')
const carregando = ref(false)
const carregandoLaunchpad = ref(false)
const criandoBranch = ref(false)
const salvandoTrace = ref(false)
const erro = ref('')
const mensagem = ref('')
const changeUrl = ref('')

function pode(acao) {
  return launchpad.value?.acoes_disponiveis?.includes(acao)
}

async function carregarWorkItems() {
  carregando.value = true
  erro.value = ''
  try {
    const { data } = await api.get('/v1/agile-runtime/work-items')
    workItems.value = data.data ?? []
    if (!selecionado.value && workItems.value.length) {
      await selecionarItem(workItems.value[0])
    }
  } catch (error) {
    erro.value = error.response?.data?.detail || 'Erro ao carregar work items.'
  } finally {
    carregando.value = false
  }
}

async function carregarLaunchpad() {
  if (!selecionado.value) return
  carregandoLaunchpad.value = true
  erro.value = ''
  try {
    const { data } = await api.get(
      `/v1/agile-runtime/work-items/${selecionado.value.id}/github-launchpad`,
      { params: { ambiente: ambiente.value } },
    )
    launchpad.value = data.data ?? null
    changeUrl.value = launchpad.value?.links?.change_request || selecionado.value?.change_url || ''
  } catch (error) {
    launchpad.value = null
    erro.value = error.response?.data?.detail || 'Erro ao carregar launchpad GitHub.'
  } finally {
    carregandoLaunchpad.value = false
  }
}

async function selecionarItem(item) {
  selecionado.value = item
  await carregarLaunchpad()
}

async function trocarAmbiente(novoAmbiente) {
  ambiente.value = novoAmbiente
  mensagem.value = ''
  await carregarLaunchpad()
}

async function criarBranchApi() {
  if (!selecionado.value) return
  criandoBranch.value = true
  erro.value = ''
  mensagem.value = ''
  try {
    const { data } = await api.post(
      `/v1/agile-runtime/work-items/${selecionado.value.id}/github/branch`,
      { ambiente: ambiente.value, criar_se_ausente: true, aplicar_branch_no_item: true },
    )
    const payload = data.data ?? data
    mensagem.value = payload.criada ? 'Branch criada via GitHub API.' : 'Branch já existia; rastreabilidade atualizada.'
    await carregarWorkItems()
    const atualizado = workItems.value.find((item) => item.id === selecionado.value.id)
    if (atualizado) selecionado.value = atualizado
    await carregarLaunchpad()
  } catch (error) {
    erro.value = error.response?.data?.detail || 'Erro ao criar branch via API.'
  } finally {
    criandoBranch.value = false
  }
}

async function salvarRastreabilidade() {
  if (!selecionado.value || !changeUrl.value) return
  salvandoTrace.value = true
  erro.value = ''
  mensagem.value = ''
  try {
    const { data } = await api.patch(
      `/v1/agile-runtime/work-items/${selecionado.value.id}/traceability`,
      {
        change_provider: 'github',
        change_url: changeUrl.value,
        branch: launchpad.value?.branch_trabalho || selecionado.value.branch,
        repositorio: launchpad.value?.repositorio || selecionado.value.repositorio,
        ambiente_deploy: ambiente.value === 'homolog' ? 'homolog' : ambiente.value,
      },
    )
    selecionado.value = data.data ?? selecionado.value
    mensagem.value = 'Rastreabilidade salva com sucesso.'
    await carregarLaunchpad()
  } catch (error) {
    erro.value = error.response?.data?.detail || 'Erro ao salvar rastreabilidade.'
  } finally {
    salvandoTrace.value = false
  }
}

onMounted(carregarWorkItems)
</script>

<style scoped>
.agile-runtime-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cabecalho {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.75rem;
  opacity: 0.7;
}

.layout {
  display: grid;
  grid-template-columns: minmax(240px, 320px) 1fr;
  gap: 16px;
}

.painel {
  border: 1px solid rgba(208, 208, 208, 0.9);
  border-radius: 12px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.02);
}

.itens {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.item-btn {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 10px 12px;
  background: transparent;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.item-btn.ativo,
.item-btn:hover {
  border-color: rgba(25, 118, 210, 0.35);
  background: rgba(25, 118, 210, 0.06);
}

.ambientes {
  display: flex;
  gap: 8px;
  margin: 12px 0;
}

.ambientes button {
  border: 1px solid rgba(208, 208, 208, 0.9);
  border-radius: 999px;
  padding: 6px 12px;
  background: transparent;
  cursor: pointer;
}

.ambientes button.ativo {
  background: rgba(25, 118, 210, 0.12);
  border-color: rgba(25, 118, 210, 0.5);
}

.meta {
  display: grid;
  gap: 8px;
  margin: 0 0 16px;
}

.meta div {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 8px;
}

.meta dt {
  opacity: 0.7;
}

.acoes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.acao {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(25, 118, 210, 0.12);
  color: inherit;
  text-decoration: none;
}

.acao.secundaria {
  background: rgba(120, 120, 120, 0.12);
}

.acao.botao {
  border: none;
  cursor: pointer;
  font: inherit;
}

.trace-form {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}

.trace-form label {
  display: grid;
  gap: 4px;
  font-size: 0.9rem;
}

.trace-form input {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(208, 208, 208, 0.9);
  background: transparent;
  color: inherit;
}

.trace-form button {
  justify-self: start;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(25, 118, 210, 0.5);
  background: rgba(25, 118, 210, 0.12);
  cursor: pointer;
}

.nota.sucesso {
  color: #1b5e20;
}

.nota.alerta-gate {
  color: #b00020;
}

.nota {
  margin-top: 12px;
  font-size: 0.9rem;
  opacity: 0.8;
}

.mono {
  font-family: monospace;
}

.alerta.erro {
  color: #b00020;
}

.vazio,
.vazio-detalhe,
.status {
  opacity: 0.8;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
