<template><section class="page"><h1>Auditoria</h1><v-card><v-card-title>Eventos recentes</v-card-title><v-card-text><v-timeline density="compact"><v-timeline-item v-for="e in eventos" :key="e.id" dot-color="amber"><strong>{{e.acao}}</strong><div class="muted">{{e.quando}} · {{e.usuario}} · {{e.correlation_id}}</div></v-timeline-item></v-timeline></v-card-text></v-card></section></template>
<script setup>
const eventos = [{id:1, acao:'REQUISITO_CRIADO', quando:'2026-04-23 19:00', usuario:'ericsonjosedossantos@tieri659.onmicrosoft.com', correlation_id:'demo-123'}]
</script>

