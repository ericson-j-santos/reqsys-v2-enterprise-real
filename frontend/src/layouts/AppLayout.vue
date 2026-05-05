<template>
  <v-layout class="req-layout">
    <!-- Mobile app bar -->
    <v-app-bar v-if="mobile" flat class="req-appbar" elevation="0" height="56">
      <v-app-bar-nav-icon color="white" @click="drawer = !drawer" />
      <span class="brand-sm ml-1">◈ ReqSys</span>
      <v-spacer />
      <v-chip size="x-small" color="amber" variant="tonal" class="mr-2">
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
      <div class="pa-5 pb-3">
        <div class="brand">◈ ReqSys</div>
        <div class="muted mt-1">SaaS Interno · v2 Enterprise</div>
      </div>
      <v-divider />

      <!-- Nav items -->
      <v-list density="compact" nav class="pt-2">
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
          <v-avatar size="30" color="amber">
            <span style="font-size:12px;font-weight:700;color:#000">
              {{ initials(auth.usuario) }}
            </span>
          </v-avatar>
          <div class="overflow-hidden">
            <div class="user-name">{{ auth.usuario.nome || auth.usuario.email }}</div>
            <div class="muted" style="font-size:11px">{{ auth.usuario.papel }}</div>
          </div>
        </div>
        <v-list density="compact" class="pb-2">
          <v-list-item
            prepend-icon="mdi-logout"
            title="Sair"
            class="nav-item"
            style="color:var(--error)!important"
            @click="sair"
          />
        </v-list>
      </template>
    </v-navigation-drawer>

    <v-main class="req-main">
      <router-view />
    </v-main>
  </v-layout>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { useAuthStore } from '../stores/auth'

const { mobile } = useDisplay()
const auth = useAuthStore()
const router = useRouter()
const drawer = ref(true)

const navItems = [
  { to: '/',                icon: 'mdi-view-dashboard',     title: 'Dashboard',       tip: 'Visão consolidada das métricas e acessos rápidos.' },
  { to: '/requisitos',      icon: 'mdi-file-document-edit', title: 'Requisitos',      tip: 'Cadastro, listagem e acompanhamento dos requisitos.' },
  { to: '/pipeline',        icon: 'mdi-pipe',               title: 'Pipeline',        tip: 'Fluxo operacional detalhado do requisito até a publicação.' },
  { to: '/qualidade-ia',    icon: 'mdi-brain',              title: 'Qualidade IA',    tip: 'Monitoramento contínuo de score e tendência de qualidade de IA.' },
  { to: '/relatorios',      icon: 'mdi-file-chart-outline', title: 'Relatórios SSRS', tip: 'Catálogo e status dos relatórios SSRS publicados.' },
  { to: '/segredos-status', icon: 'mdi-key-chain-variant',  title: 'Segredos',        tip: 'Diagnóstico da origem dos segredos do backend.' },
  { to: '/rastreabilidade', icon: 'mdi-vector-link',        title: 'Rastreabilidade', tip: 'Matriz de vínculo entre requisito, história e entrega.' },
  { to: '/auditoria',       icon: 'mdi-shield-search',      title: 'Auditoria',       tip: 'Linha do tempo de eventos e governança operacional.' },
]

function initials(u) {
  return (u.nome || u.email || '?')[0].toUpperCase()
}

function sair() {
  auth.sair()
  router.push('/login')
}
</script>

