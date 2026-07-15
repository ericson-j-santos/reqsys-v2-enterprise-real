<template>
  <v-app>
    <UserExperienceGuardrails v-if="$route.path !== '/login'" />
    <RouteFeedback v-if="$route.path !== '/login'" />
    <UserJourneyFeedback v-if="$route.path !== '/login'" />
    <GovBIEmptyStateBridge v-if="$route.path !== '/login'" />
    <AppLayout v-if="$route.path !== '/login'" />
    <router-view v-else />
  </v-app>
</template>
<script setup>
import AppLayout from './layouts/AppLayout.vue'
import GovBIEmptyStateBridge from './components/GovBIEmptyStateBridge.vue'
import RouteFeedback from './components/RouteFeedback.vue'
import UserExperienceGuardrails from './components/UserExperienceGuardrails.vue'
import UserJourneyFeedback from './components/UserJourneyFeedback.vue'
</script>