<template>
  <v-app>
    <template v-if="!$route.meta.standalone && $route.path !== '/login'">
      <UserExperienceGuardrails />
      <RouteFeedback />
      <UserJourneyFeedback />
      <DashboardEmptyStateBridge />
      <AppLayout />
    </template>
    <router-view v-else />
  </v-app>
</template>
<script setup>
import AppLayout from './layouts/AppLayout.vue'
import DashboardEmptyStateBridge from './components/DashboardEmptyStateBridge.vue'
import RouteFeedback from './components/RouteFeedback.vue'
import UserExperienceGuardrails from './components/UserExperienceGuardrails.vue'
import UserJourneyFeedback from './components/UserJourneyFeedback.vue'
</script>
