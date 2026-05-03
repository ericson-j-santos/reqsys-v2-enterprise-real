<template><section class="page"><h1>Matriz de Rastreabilidade</h1><v-card><v-table><thead><tr><th>Requisito</th><th>História</th><th>Redmine</th><th>Planner</th><th>Commit</th><th>Status</th></tr></thead><tbody><tr v-for="r in linhas" :key="r.req"><td>{{r.req}}</td><td>{{r.historia}}</td><td>{{r.redmine}}</td><td>{{r.planner}}</td><td>{{r.commit}}</td><td><v-chip size="small" color="green">{{r.status}}</v-chip></td></tr></tbody></v-table></v-card></section></template>
<script setup>
const linhas = [{req:'REQ-0001', historia:'US-0001', redmine:'#42', planner:'PLN-104', commit:'abc1234', status:'rastreado'}]
</script>
