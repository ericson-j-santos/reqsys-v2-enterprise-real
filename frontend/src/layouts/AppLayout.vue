<template>
  <v-layout class="req-layout">
    <!-- Mobile app bar -->
    <v-app-bar v-if="mobile" flat class="req-appbar" elevation="0" height="56">
      <v-app-bar-nav-icon color="white" aria-label="Abrir menu de navegação" @click="drawer = !drawer" />
      <span class="brand-sm ml-1">◈ ReqSys</span>
      <v-spacer />
      <v-chip size="x-small" color="amber" variant="tonal" class="mr-2 req-role-chip">
        {{ auth.usuario?.papel || 'user' }}
      </v-chip>
    </v-app-bar>

    <!-- Navigation drawer -->
    <v-navigation-drawer
      v-model="drawer"
      :permanent="!mobile"
      :temporary="mobile"
      width="260"
      class="req-drawer"
    >
      <!-- Brand -->
      <div class="pa-5 pb-3 req-brand-block">
        <div class="brand">◈ ReqSys</div>
        <div class="muted mt-1">SaaS Interno · v2 Enterprise</div>
      </div>
      <v-divider />

      <!-- Nav items -->
      <v-list density="compact" nav class="pt-2 req-nav-list" aria-label="Navegação principal">
        <v-tooltip
          v-for="item in navItems"
          :key="item.to"
          :text="item.tip"
          location="right"
        >
          <template #activator="{ props }">
            <v-list-item
              v-bind="props"
              :to="item.to"
              :prepend-icon="item.icon"
              :title="item.title"
              class="nav-item"
              @click="mobile && (drawer = false)"
            />
          </template>
        </v-tooltip>
      </v-list>

      <!-- User + logout -->
      <template #append>
        <v-divider />
        <div v-if="auth.usuario" class="user-info">
          <v-avatar size="30" color="amber" aria-hidden="true">
            <span class="user-initials">
              {{ initials(auth.usuario) }}
            </span>
          </v-avatar>
          <div class="overflow-hidden">
            <div class="user-name">{{ auth.usuario.nome || auth.usuario.email }}</div>
            <div class="muted user-role">{{ auth.usuario.papel }}</div>
          </div>
        </div>
        <v-list density="compact" class="pb-2">
          <v-list-item
            prepend-icon="mdi-logout"
            title="Sair"
            class="nav-item logout-item"
            @click="sair"
          />
        </v-list>
      </template>
    </v-navigation-drawer>

    <v-main class="req-main">
      <div class="req-content-shell">
        <router-view />
      </div>
    </v-main>
  </v-layout>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { useAuthStore } from '../stores/auth'

const { mobile } = useDisplay()
const auth = useAuthStore()
const router = useRouter()
const drawer = ref(!mobile.value)

watch(mobile, (isMobile) => {
  drawer.value = !isMobile
})

const navItems = [
  { to: '/',                icon: 'mdi-view-dashboard',     title: 'Dashboard',       tip: 'Visão consolidada das métricas e acessos rápidos.' },
  { to: '/monitoramento-operacional', icon: 'mdi-monitor-dashboard', title: 'Monitoramento', tip: 'Estado operacional de PRs, gates, integrações e pendências.' },
  { to: '/requisitos',      icon: 'mdi-file-document-edit', title: 'Requisitos',      tip: 'Cadastro, listagem e acompanhamento dos requisitos.' },
  { to: '/pipeline',        icon: 'mdi-pipe',               title: 'Pipeline',        tip: 'Fluxo operacional detalhado do requisito até a publicação.' },
  { to: '/task-console',    icon: 'mdi-clipboard-check-outline', title: 'Task Console', tip: 'Console web para revisar tarefas e preparar envio ao Planner.' },
  { to: '/qualidade-ia',    icon: 'mdi-brain',              title: 'Qualidade IA',    tip: 'Monitoramento contínuo de score e tendência de qualidade de IA.' },
  { to: '/recomendacoes-ia', icon: 'mdi-robot-outline',     title: 'Recomendações IA', tip: 'Criação, decisão e outcome de recomendações geradas por IA.' },
  { to: '/relatorios',      icon: 'mdi-file-chart-outline', title: 'Relatórios SSRS', tip: 'Catálogo e status dos relatórios SSRS publicados.' },
  { to: '/segredos-status', icon: 'mdi-key-chain-variant',  title: 'Segredos',        tip: 'Diagnóstico da origem dos segredos do backend.' },
  { to: '/rastreabilidade', icon: 'mdi-vector-link',        title: 'Rastreabilidade', tip: 'Matriz de vínculo entre requisito, história e entrega.' },
  { to: '/specs',            icon: 'mdi-file-code-outline',  title: 'Specs SDD',       tip: 'Especificações de features do my-first-spec-project.' },
  { to: '/auditoria',       icon: 'mdi-shield-search',      title: 'Auditoria',       tip: 'Linha do tempo de eventos e governança operacional.' },
  { to: '/hub-lowcode',       icon: 'mdi-lightning-bolt-circle',    title: 'Hub Low-Code',   tip: 'Pacotes IA, flows Power Automate, bot ReqSysAgent e pipeline GitHub ALM.' },
  { to: '/painel-integracao', icon: 'mdi-view-dashboard-outline',  title: 'Integrações',    tip: 'Painel de acompanhamento: Planner, Teams e histórico de eventos.' },
  { to: '/figma-github',      icon: 'mdi-vector-square',           title: 'Figma GitHub',   tip: 'Sincronização e retorno em tela entre Figma e GitHub.' },
  { to: '/arquitetura',       icon: 'mdi-sitemap',                  title: 'Mapa da Solução', tip: 'Visão completa de todos os componentes Web e Low-Code.' },
  { to: '/governanca',        icon: 'mdi-shield-check-outline',     title: 'Governança',     tip: 'Padrão Ouro Enterprise: gates, CI/CD, observabilidade, analytics e IA auditável.' },
  { to: '/govbi-ia',      icon: 'mdi-database-search',    title: 'GovBI IA',        tip: 'Consultas analíticas em linguagem natural com IA governada.' },
]

function initials(u) {
  return (u.nome || u.email || '?')[0].toUpperCase()
}

function sair() {
  auth.sair()
  router.push('/login')
}
</script>

<style scoped>
.req-appbar {
  background: var(--accent) !important;
}
.brand-sm {
  color: #fff;
  font-weight: 800;
  font-size: 16px;
  letter-spacing: -0.01em;
}
.req-brand-block {
  min-width: 0;
}
.req-nav-list {
  max-height: calc(100vh - 176px);
  overflow-y: auto;
}
.nav-item {
  border-radius: 8px;
  margin-bottom: 2px;
}
.logout-item {
  color: var(--error) !important;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  min-width: 0;
}
.user-initials {
  font-size: 12px;
  font-weight: 700;
  color: #000;
}
.user-name {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.user-role {
  font-size: 11px;
}
.req-content-shell {
  min-width: 0;
  width: 100%;
}

@media (max-width: 600px) {
  .req-role-chip {
    max-width: 96px;
  }

  .req-main {
    padding-top: 56px;
  }
}
</style>
