<template>
  <section class="page" data-testid="route-specs">

    <!-- Cabeçalho -->
    <div class="page-header">
      <div>
        <h1>Specs SDD</h1>
        <p class="muted">Especificações de features · my-first-spec-project</p>
      </div>
      <v-btn color="amber" variant="tonal" prepend-icon="mdi-plus" @click="dialogNova = true">
        Nova Feature
      </v-btn>
    </div>

    <!-- Loading / erro de config -->
    <v-alert v-if="erroConfig" type="warning" variant="tonal" class="mb-4">
      <strong>SDD_SPECS_PATH não configurado.</strong>
      Adicione ao <code>.env</code> do backend:
      <code>SDD_SPECS_PATH=../../my-first-spec-project/.sdd</code>
    </v-alert>

    <!-- Layout principal: sidebar + conteúdo -->
    <div class="specs-layout" v-if="!erroConfig">

      <!-- Sidebar de features -->
      <v-card class="specs-sidebar" elevation="0">
        <v-card-title class="sidebar-title">
          <v-icon size="16" class="mr-1">mdi-folder-multiple-outline</v-icon>
          Features
          <v-chip size="x-small" color="amber" variant="tonal" class="ml-auto">
            {{ specs.length }}
          </v-chip>
        </v-card-title>

        <v-text-field
          v-model="busca"
          placeholder="Filtrar..."
          density="compact"
          variant="plain"
          hide-details
          prepend-inner-icon="mdi-magnify"
          class="px-3 pb-2"
        />

        <v-divider />

        <v-list density="compact" nav class="pt-1">
          <v-list-item
            v-for="s in specsFiltradas"
            :key="s.slug"
            :active="featureSelecionada === s.slug"
            active-color="amber"
            @click="selecionarFeature(s.slug)"
          >
            <template #prepend>
              <v-icon size="16">mdi-file-document-multiple-outline</v-icon>
            </template>
            <v-list-item-title class="text-body-2">{{ s.slug }}</v-list-item-title>
            <template #append>
              <div class="file-chips">
                <v-chip
                  v-for="arq in s.arquivos"
                  :key="arq"
                  size="x-small"
                  :color="corArquivo(arq)"
                  variant="tonal"
                >{{ arq.replace('.md','') }}</v-chip>
              </div>
            </template>
          </v-list-item>

          <v-list-item v-if="specsFiltradas.length === 0" disabled>
            <v-list-item-title class="muted text-body-2">Nenhuma feature encontrada</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-card>

      <!-- Painel de conteúdo -->
      <v-card class="specs-content" elevation="0">

        <!-- Estado vazio -->
        <div v-if="!featureSelecionada" class="empty-state">
          <v-icon size="64" color="grey-darken-1">mdi-file-document-outline</v-icon>
          <p class="muted mt-2">Selecione uma feature para visualizar</p>
        </div>

        <!-- Conteúdo da feature -->
        <template v-else>
          <div class="content-header">
            <div>
              <h2 class="feature-title">{{ featureSelecionada }}</h2>
              <div class="d-flex ga-1 mt-1">
                <v-chip
                  v-for="arq in specAtual?.arquivos ? Object.keys(specAtual.arquivos) : []"
                  :key="arq"
                  size="x-small"
                  :color="corArquivo(arq + '.md')"
                  variant="tonal"
                >{{ arq }}</v-chip>
              </div>
            </div>
            <div class="d-flex ga-2">
              <v-btn
                v-if="!editando"
                size="small"
                variant="tonal"
                color="amber"
                prepend-icon="mdi-pencil"
                @click="iniciarEdicao"
              >Editar</v-btn>
              <template v-else>
                <v-btn size="small" variant="tonal" color="grey" prepend-icon="mdi-close" @click="cancelarEdicao">Cancelar</v-btn>
                <v-btn size="small" variant="flat" color="amber" prepend-icon="mdi-content-save" :loading="salvando" @click="salvar">Salvar</v-btn>
              </template>
            </div>
          </div>

          <v-divider />

          <!-- Tabs de arquivos -->
          <v-tabs v-model="tabAtiva" color="amber" density="compact" class="px-4">
            <v-tab
              v-for="arq in Object.keys(specAtual?.arquivos || {})"
              :key="arq"
              :value="arq"
            >
              <v-icon size="14" class="mr-1">{{ iconArquivo(arq) }}</v-icon>
              {{ arq }}
            </v-tab>
          </v-tabs>

          <v-divider />

          <!-- Conteúdo da aba -->
          <div class="content-body">
            <v-window v-model="tabAtiva">
              <v-window-item
                v-for="(conteudo, arq) in specAtual?.arquivos"
                :key="arq"
                :value="arq"
              >
                <!-- Modo edição -->
                <v-textarea
                  v-if="editando"
                  v-model="conteudoEditado[arq]"
                  variant="outlined"
                  rows="28"
                  hide-details
                  class="editor-area ma-4"
                  font-family="monospace"
                />
                <!-- Modo leitura: markdown renderizado -->
                <div
                  v-else
                  class="markdown-body"
                  v-html="renderMarkdown(conteudo)"
                />
              </v-window-item>
            </v-window>
          </div>
        </template>

      </v-card>
    </div>

    <!-- Dialog: Nova Feature -->
    <v-dialog v-model="dialogNova" max-width="560" persistent>
      <v-card>
        <v-card-title class="d-flex align-center ga-2 pa-5 pb-3">
          <v-icon color="amber">mdi-plus-circle-outline</v-icon>
          Nova Feature
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-5">

          <v-text-field
            v-model="nova.titulo"
            label="Título da feature *"
            placeholder="ex: Autenticação de Usuários"
            variant="outlined"
            density="compact"
            class="mb-3"
            @update:model-value="gerarSlug"
          />
          <v-text-field
            v-model="nova.slug"
            label="Slug / pasta *"
            placeholder="ex: user-auth"
            variant="outlined"
            density="compact"
            class="mb-3"
            hint="Gerado automaticamente a partir do título"
          />
          <v-text-field
            v-model="nova.descricao"
            label="Descrição breve"
            variant="outlined"
            density="compact"
            class="mb-3"
          />
          <v-text-field
            v-model="nova.autor"
            label="Autor"
            variant="outlined"
            density="compact"
            class="mb-4"
          />

          <v-divider class="mb-4" />

          <p class="text-body-2 muted mb-2">Base de criação:</p>
          <v-radio-group v-model="nova.modo" density="compact" class="mb-3">
            <v-radio label="Clonar exemplo existente" value="exemplo" color="amber" />
            <v-radio label="Templates em branco" value="template" color="amber" />
          </v-radio-group>

          <v-select
            v-if="nova.modo === 'exemplo'"
            v-model="nova.exemplo_base"
            :items="specs.map(s => s.slug)"
            label="Exemplo base *"
            variant="outlined"
            density="compact"
            class="mb-3"
          />

          <v-checkbox-btn
            v-if="nova.modo === 'template'"
            v-for="tpl in templatesDisponiveis"
            :key="tpl"
            v-model="nova.templates"
            :label="tpl"
            :value="tpl"
            color="amber"
            density="compact"
          />

        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="fecharDialogNova">Cancelar</v-btn>
          <v-btn
            color="amber"
            variant="flat"
            :loading="criando"
            :disabled="!nova.titulo || !nova.slug"
            @click="criarFeature"
          >Criar Feature</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar feedback -->
    <v-snackbar v-model="snack.visivel" :color="snack.cor" timeout="3000" location="bottom right">
      {{ snack.msg }}
    </v-snackbar>

  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../services/api'

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------

const specs              = ref([])
const templatesDisponiveis = ref([])
const featureSelecionada = ref(null)
const specAtual          = ref(null)
const tabAtiva           = ref(null)
const busca              = ref('')
const editando           = ref(false)
const salvando           = ref(false)
const criando            = ref(false)
const erroConfig         = ref(false)
const dialogNova         = ref(false)
const conteudoEditado    = ref({})

const nova = ref({
  titulo: '', slug: '', descricao: '', autor: '',
  modo: 'template', exemplo_base: null, templates: ['requirements', 'design'],
})

const snack = ref({ visivel: false, msg: '', cor: 'success' })

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const specsFiltradas = computed(() =>
  specs.value.filter(s => s.slug.includes(busca.value.toLowerCase()))
)

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

onMounted(async () => {
  await carregarSpecs()
  await carregarTemplates()
})

async function carregarSpecs() {
  try {
    const { data } = await api.get('/v1/specs')
    specs.value = data.data || []
    erroConfig.value = false
  } catch (e) {
    if (e?.response?.status === 503) erroConfig.value = true
    specs.value = []
  }
}

async function carregarTemplates() {
  try {
    const { data } = await api.get('/v1/specs/templates')
    templatesDisponiveis.value = data.data || []
  } catch {
    templatesDisponiveis.value = ['requirements', 'design', 'tasks', 'research']
  }
}

async function selecionarFeature(slug) {
  featureSelecionada.value = slug
  editando.value = false
  specAtual.value = null
  try {
    const { data } = await api.get(`/v1/specs/${slug}`)
    specAtual.value = data.data
    const arqs = Object.keys(data.data?.arquivos || {})
    tabAtiva.value = arqs[0] || null
  } catch {
    mostrarSnack('Erro ao carregar feature', 'error')
  }
}

// ---------------------------------------------------------------------------
// Edição
// ---------------------------------------------------------------------------

function iniciarEdicao() {
  conteudoEditado.value = { ...specAtual.value?.arquivos }
  editando.value = true
}

function cancelarEdicao() {
  editando.value = false
  conteudoEditado.value = {}
}

async function salvar() {
  salvando.value = true
  try {
    for (const [arq, conteudo] of Object.entries(conteudoEditado.value)) {
      await api.put(`/v1/specs/${featureSelecionada.value}/${arq}.md`, { conteudo })
    }
    specAtual.value.arquivos = { ...conteudoEditado.value }
    editando.value = false
    mostrarSnack('Spec salvo com sucesso')
  } catch {
    mostrarSnack('Erro ao salvar', 'error')
  } finally {
    salvando.value = false
  }
}

// ---------------------------------------------------------------------------
// Criação
// ---------------------------------------------------------------------------

function gerarSlug() {
  const s = nova.value.titulo
    .normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
  nova.value.slug = s
}

async function criarFeature() {
  criando.value = true
  try {
    const payload = {
      slug: nova.value.slug,
      titulo: nova.value.titulo,
      descricao: nova.value.descricao,
      autor: nova.value.autor,
      exemplo_base: nova.value.modo === 'exemplo' ? nova.value.exemplo_base : null,
      templates: nova.value.modo === 'template' ? nova.value.templates : [],
    }
    await api.post('/v1/specs', payload)
    mostrarSnack(`Feature "${nova.value.slug}" criada`)
    fecharDialogNova()
    await carregarSpecs()
    selecionarFeature(nova.value.slug)
  } catch (e) {
    const msg = e?.response?.data?.errors?.[0]?.message || 'Erro ao criar feature'
    mostrarSnack(msg, 'error')
  } finally {
    criando.value = false
  }
}

function fecharDialogNova() {
  dialogNova.value = false
  nova.value = { titulo: '', slug: '', descricao: '', autor: '', modo: 'template', exemplo_base: null, templates: ['requirements', 'design'] }
}

// ---------------------------------------------------------------------------
// Markdown renderer
// ---------------------------------------------------------------------------

function renderMarkdown(md) {
  if (!md) return ''
  let html = md
    // Remove bloco HTML de comentários (cabeçalho gerado)
    .replace(/<!--[\s\S]*?-->/g, '')
    // Mermaid: preserva como bloco de código estilizado
    .replace(/```mermaid([\s\S]*?)```/g, '<pre class="mermaid-block"><code>mermaid$1</code></pre>')
    // Blocos de código
    .replace(/```([\s\S]*?)```/g, '<pre class="code-block"><code>$1</code></pre>')
    // Código inline
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Negrito e itálico
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Links — REQ-XXXXX linkados ao ReqSys
    .replace(/\b(REQ-\d+)\b/g, '<a href="/requisitos" class="req-link" title="Ver requisitos">$1</a>')
    // Links externos
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // Tabelas
    .replace(/^\|(.+)\|$/gm, (_, row) => {
      const cells = row.split('|').map(c => c.trim())
      const isHeader = cells.some(c => /^[-:]+$/.test(c))
      if (isHeader) return ''
      const tag = 'td'
      return `<tr>${cells.map(c => `<${tag}>${c}</${tag}>`).join('')}</tr>`
    })
    // HR
    .replace(/^---+$/gm, '<hr>')
    // Listas
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
    // Parágrafos
    .replace(/\n{2,}/g, '</p><p>')

  // Wrap em tabela se tem <tr>
  if (html.includes('<tr>')) {
    html = html.replace(/((<tr>.*<\/tr>\s*)+)/gs, '<table class="md-table">$1</table>')
  }
  // Wrap listas
  html = html.replace(/((<li>.*<\/li>\s*)+)/gs, '<ul>$1</ul>')

  return `<p>${html}</p>`
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

function corArquivo(nome) {
  if (nome.includes('requirements')) return 'blue'
  if (nome.includes('design'))       return 'purple'
  if (nome.includes('tasks'))        return 'green'
  if (nome.includes('research'))     return 'orange'
  return 'grey'
}

function iconArquivo(nome) {
  if (nome.includes('requirements')) return 'mdi-clipboard-list-outline'
  if (nome.includes('design'))       return 'mdi-pencil-ruler'
  if (nome.includes('tasks'))        return 'mdi-check-all'
  if (nome.includes('research'))     return 'mdi-magnify'
  return 'mdi-file-document-outline'
}

function mostrarSnack(msg, cor = 'success') {
  snack.value = { visivel: true, msg, cor }
}
</script>

<style scoped>
.specs-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  min-height: 70vh;
}

/* Sidebar */
.specs-sidebar {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--v-theme-on-surface);
  display: flex;
  align-items: center;
  padding: 12px 16px 8px;
}

.file-chips {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
}

/* Conteúdo */
.specs-content {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
}

.content-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 16px 20px;
  gap: 12px;
}

.feature-title {
  font-size: 16px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
}

.content-body {
  flex: 1;
  overflow: auto;
}

/* Editor */
.editor-area :deep(textarea) {
  font-family: 'Fira Code', 'Courier New', monospace !important;
  font-size: 13px !important;
  line-height: 1.6 !important;
}

/* Markdown */
.markdown-body {
  padding: 20px 28px;
  line-height: 1.7;
  font-size: 14px;
  color: rgba(255,255,255,0.87);
}

.markdown-body :deep(h1) {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 16px;
  color: rgba(255,255,255,0.95);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding-bottom: 8px;
}

.markdown-body :deep(h2) {
  font-size: 17px;
  font-weight: 600;
  margin: 24px 0 10px;
  color: rgba(255,255,255,0.9);
}

.markdown-body :deep(h3) {
  font-size: 14px;
  font-weight: 600;
  margin: 16px 0 6px;
  color: rgba(255,193,7,0.9);
}

.markdown-body :deep(p) {
  margin: 0 0 10px;
}

.markdown-body :deep(ul) {
  padding-left: 20px;
  margin: 6px 0 10px;
}

.markdown-body :deep(li) {
  margin: 3px 0;
}

.markdown-body :deep(strong) {
  color: rgba(255,255,255,0.95);
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid rgba(255,255,255,0.08);
  margin: 20px 0;
}

.markdown-body :deep(.inline-code) {
  background: rgba(255,255,255,0.08);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}

.markdown-body :deep(.code-block) {
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  padding: 12px 16px;
  margin: 12px 0;
  overflow-x: auto;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}

.markdown-body :deep(.mermaid-block) {
  background: rgba(255,193,7,0.05);
  border: 1px solid rgba(255,193,7,0.2);
  border-radius: 6px;
  padding: 12px 16px;
  margin: 12px 0;
  font-size: 12px;
  color: rgba(255,193,7,0.8);
}

.markdown-body :deep(.req-link) {
  color: #ffc107;
  text-decoration: none;
  font-weight: 600;
  border-bottom: 1px dashed rgba(255,193,7,0.4);
}

.markdown-body :deep(.req-link:hover) {
  border-bottom-style: solid;
}

.markdown-body :deep(.md-table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
  font-size: 13px;
}

.markdown-body :deep(.md-table td) {
  border: 1px solid rgba(255,255,255,0.1);
  padding: 6px 10px;
}

.markdown-body :deep(.md-table tr:first-child td) {
  background: rgba(255,255,255,0.05);
  font-weight: 600;
}
</style>
