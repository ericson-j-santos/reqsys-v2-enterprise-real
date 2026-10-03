<template>
  <section class="pulso" data-testid="route-painel-projetos" aria-labelledby="pulso-title">
    <header class="pulso-header">
      <div>
        <p class="pulso-brand">〽 <strong>Pulso</strong> · {{ ambiente }}</p>
        <h1 id="pulso-title">Visão geral</h1>
        <p>Acompanhe o que avançou, o que precisa de atenção e as evidências dos projetos.</p>
      </div>
      <div class="pulso-actions">
        <v-text-field v-model="busca" label="Buscar projeto" prepend-inner-icon="mdi-magnify" density="compact" variant="outlined" hide-details clearable />
        <v-btn color="primary" prepend-icon="mdi-refresh" :loading="carregando" @click="carregar">Atualizar</v-btn>
      </div>
    </header>

    <v-alert v-if="erro" type="error" variant="tonal" closable>{{ erro }}</v-alert>
    <v-alert v-else-if="itensSemProjeto" type="warning" variant="tonal">
      {{ itensSemProjeto }} item(ns) de execução ainda não aparecem no portfólio porque não possuem projeto/repositório vinculado.
    </v-alert>

    <div class="metrics">
      <article><v-icon icon="mdi-briefcase-outline"/><strong>{{ projetos.length }}</strong><span>ativos</span></article>
      <article><v-icon icon="mdi-progress-check"/><strong>{{ progressoMedio }}%</strong><span>progresso médio</span></article>
      <article><v-icon icon="mdi-alert-outline"/><strong>{{ emAtencao }}</strong><span>precisam de atenção</span></article>
      <article><v-icon icon="mdi-link-variant"/><strong>{{ comEvidencia }}</strong><span>com evidência</span></article>
    </div>

    <section class="portfolio-card">
      <div class="section-title"><div><h2>Panorama do portfólio</h2><p>Projetos atuais consolidados pelo repositório informado no Agile Execução.</p></div><span>Sincronizado {{ sincronizadoEm }}</span></div>
      <div class="portfolio-bar" role="img" aria-label="Distribuição da saúde dos projetos">
        <span class="ok" :style="{ flex: distribuicao.ritmo || 0.1 }"/><span class="warn" :style="{ flex: distribuicao.atencao || 0.1 }"/><span class="late" :style="{ flex: distribuicao.atrasado || 0.1 }"/><span class="done" :style="{ flex: distribuicao.concluido || 0.1 }"/>
      </div>
      <div class="legend"><span>● No ritmo <b>{{ distribuicao.ritmo }}</b></span><span>● Em atenção <b>{{ distribuicao.atencao }}</b></span><span>● Atrasados <b>{{ distribuicao.atrasado }}</b></span><span>● Concluídos <b>{{ distribuicao.concluido }}</b></span></div>
    </section>

    <section class="portfolio-card">
      <div class="section-title"><div><h2>Projetos em andamento</h2><p>{{ projetosFiltrados.length }} projetos encontrados</p></div><v-chip size="small" color="info">Origem: execução atual</v-chip></div>
      <div class="project-table-wrap">
        <table class="project-table">
          <thead><tr><th>Projeto</th><th>Responsável</th><th>Progresso</th><th>Próximo marco</th><th>Ambiente</th><th>Situação</th></tr></thead>
          <tbody>
            <tr v-for="projeto in projetosFiltrados" :key="projeto.id" @click="selecionado = projeto.id" :class="{ selected: selecionado === projeto.id }">
              <td><strong>{{ projeto.name }}</strong><small>{{ projeto.code }}</small></td>
              <td>{{ projeto.owner }}</td>
              <td><div class="progress-cell"><v-progress-linear :model-value="projeto.progress" :color="corSaude(projeto.health)" height="8" rounded/><span>{{ projeto.progress }}%</span></div></td>
              <td>{{ projeto.nextMilestone }}</td><td>{{ projeto.environment }}</td>
              <td><v-chip size="small" :color="corSaude(projeto.health)" variant="tonal">{{ projeto.health }}</v-chip></td>
            </tr>
            <tr v-if="!projetosFiltrados.length"><td colspan="6" class="empty">Nenhum projeto publicado pelas fontes atuais.</td></tr>
          </tbody>
        </table>
      </div>
      <article v-if="projetoSelecionado" class="project-detail">
        <div><h3>{{ projetoSelecionado.name }}</h3><p>{{ projetoSelecionado.summary || 'Sem resumo publicado.' }}</p></div>
        <dl><div><dt>Origem</dt><dd>{{ projetoSelecionado.origin }}</dd></div><div><dt>Última sincronização</dt><dd>{{ formatarData(projetoSelecionado.updatedAt) }}</dd></div><div><dt>Itens / requisitos</dt><dd>{{ projetoSelecionado.workItems }} / {{ projetoSelecionado.requirements }}</dd></div><div><dt>Branch</dt><dd>{{ projetoSelecionado.branch || 'Não vinculada' }}</dd></div><div><dt>Issue / PR</dt><dd>{{ projetoSelecionado.changeId || 'Não vinculada' }}</dd></div><div><dt>Planner task</dt><dd>{{ projetoSelecionado.plannerTaskId || 'Não vinculada' }}</dd></div><div><dt>Correlação</dt><dd>{{ projetoSelecionado.correlationId || 'Não informada' }}</dd></div></dl>
        <a v-if="projetoSelecionado.evidenceUrl" :href="projetoSelecionado.evidenceUrl" target="_blank" rel="noreferrer">Abrir evidência ↗</a>
      </article>
    </section>

    <section class="portfolio-card">
      <div class="section-title"><div><h2>Soluções em destaque</h2><p>Capacidades dos requisitos ligados aos projetos atuais.</p></div></div>
      <div class="solutions"><article v-for="solucao in solucoes" :key="solucao.name"><div><strong>{{ solucao.name }}</strong><small>{{ solucao.projects }} projeto(s) · {{ solucao.owner }}</small></div><div class="progress-cell"><v-progress-linear :model-value="solucao.progress" color="success" height="8" rounded/><span>{{ solucao.progress }}%</span></div></article></div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../services/api'
import { buildPulsoPortfolio } from '../services/painelProjetos'

const ambiente = (import.meta.env.VITE_APP_ENVIRONMENT || 'DEV').toUpperCase()
const projetos = ref([]), solucoes = ref([]), busca = ref(''), selecionado = ref(null), erro = ref(''), carregando = ref(false), sincronizado = ref(null), itensSemProjeto = ref(0)
const projetosFiltrados = computed(() => { const q = busca.value?.trim().toLocaleLowerCase('pt-BR'); return q ? projetos.value.filter(p => `${p.name} ${p.code} ${p.owner} ${p.solution}`.toLocaleLowerCase('pt-BR').includes(q)) : projetos.value })
const projetoSelecionado = computed(() => projetos.value.find(p => p.id === selecionado.value))
const progressoMedio = computed(() => projetos.value.length ? Math.round(projetos.value.reduce((s,p) => s + p.progress, 0) / projetos.value.length) : 0)
const emAtencao = computed(() => projetos.value.filter(p => ['Em atenção','Atrasado'].includes(p.health)).length)
const comEvidencia = computed(() => projetos.value.filter(p => p.evidenceUrl).length)
const distribuicao = computed(() => ({ ritmo: projetos.value.filter(p=>p.health==='No ritmo').length, atencao: projetos.value.filter(p=>p.health==='Em atenção').length, atrasado: projetos.value.filter(p=>p.health==='Atrasado').length, concluido: projetos.value.filter(p=>p.health==='Concluído').length }))
const sincronizadoEm = computed(() => sincronizado.value ? formatarData(sincronizado.value) : 'aguardando')
function corSaude(saude) { return ({'No ritmo':'success','Em atenção':'warning','Atrasado':'error','Concluído':'blue-grey'})[saude] || 'grey' }
function formatarData(value) { if (!value) return 'Não informada'; const d = new Date(value); return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('pt-BR') }
function payload(response) { return response?.data?.data ?? response?.data ?? [] }
async function carregar() {
  carregando.value = true; erro.value = ''
  try {
    const [req, work, trace] = await Promise.all([api.get('/v1/requisitos'), api.get('/v1/agile-runtime/work-items'), api.get('/v1/rastreabilidade/matriz', { params: { limit: 100 } })])
    const result = buildPulsoPortfolio(payload(req), payload(work), payload(trace)?.linhas || [], ambiente)
    projetos.value = result.projects; solucoes.value = result.solutions; itensSemProjeto.value = result.unlinkedWorkItems; selecionado.value = projetos.value.some(p => p.id === selecionado.value) ? selecionado.value : projetos.value[0]?.id || null; sincronizado.value = new Date().toISOString()
  } catch (e) { erro.value = e.response?.data?.detail || 'Não foi possível consolidar as fontes do Painel de projetos.' }
  finally { carregando.value = false }
}
onMounted(carregar)
</script>

<style scoped>
.pulso{--pulso:#ff4d55;display:flex;flex-direction:column;gap:20px;padding:var(--space-md);color:var(--text)}.pulso-header,.section-title{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;flex-wrap:wrap}.pulso-brand{color:var(--pulso);font-size:var(--font-size-lg)}.pulso-header h1{font-size:var(--font-size-display);margin:var(--space-xs) 0}.pulso-header p,.section-title p{color:var(--muted);margin:0}.pulso-actions{display:flex;gap:10px;align-items:center;min-width:min(100%,420px)}.pulso-actions .v-input{min-width:250px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);border-block:1px solid var(--line)}.metrics article{display:grid;grid-template-columns:auto auto 1fr;align-items:center;gap:10px;padding:var(--space-xl);border-right:1px solid var(--line)}.metrics strong{font-size:var(--font-size-display)}.metrics span{color:var(--muted)}.portfolio-card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:var(--space-xl)}.section-title h2{margin:0 0 var(--space-xs)}.section-title>span{font-size:var(--font-size-sm);color:var(--muted)}.portfolio-bar{display:flex;height:18px;border-radius:20px;overflow:hidden;margin:var(--space-xl) 0 var(--space-md)}.portfolio-bar .ok{background:#35b779}.portfolio-bar .warn{background:#ffbd3d}.portfolio-bar .late{background:#ff5058}.portfolio-bar .done{background:#aeb8c5}.legend{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--muted)}.legend b{color:var(--text);margin-left:var(--space-sm)}.project-table-wrap{overflow:auto;margin-top:var(--space-lg)}.project-table{width:100%;border-collapse:collapse;min-width:820px}.project-table th,.project-table td{text-align:left;padding:var(--space-md);border-bottom:1px solid var(--line)}.project-table th{font-size:var(--font-size-sm);color:var(--muted)}.project-table tr{cursor:pointer}.project-table tr.selected{background:rgba(255,77,85,.08);border-left:3px solid var(--pulso)}.project-table td small,.solutions small{display:block;color:var(--muted);margin-top:var(--space-xs)}.progress-cell{display:grid;grid-template-columns:minmax(80px,1fr) auto;gap:9px;align-items:center}.empty{text-align:center!important;color:var(--muted)}.project-detail{margin-top:var(--space-lg);border-left:4px solid var(--pulso);background:rgba(255,77,85,.06);padding:var(--space-lg);border-radius:8px}.project-detail h3{margin:0}.project-detail dl{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.project-detail dt{font-size:var(--font-size-xs);color:var(--muted)}.project-detail dd{margin:var(--space-xs) 0;word-break:break-word}.project-detail a{color:var(--pulso);font-weight:700}.solutions article{display:grid;grid-template-columns:minmax(220px,1fr) minmax(180px,320px);gap:20px;padding:var(--space-lg);border-bottom:1px solid var(--line);align-items:center}@media(max-width:900px){.metrics{grid-template-columns:repeat(2,1fr)}.project-detail dl{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.metrics{grid-template-columns:1fr}.metrics article{border-right:0}.pulso-actions{flex-direction:column;align-items:stretch}.pulso-actions .v-input{min-width:0}.project-detail dl{grid-template-columns:1fr}.solutions article{grid-template-columns:1fr}}
</style>
