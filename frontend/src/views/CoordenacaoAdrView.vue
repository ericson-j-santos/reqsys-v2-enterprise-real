<template>
  <CoordenacaoDashboard
    data-testid="route-coordenacao-adr"
    base-path="/v1/agents/adr-orchestrator"
    variante="adr"
    titulo="Coordenação Geral de Decisões de Arquitetura"
    subtitulo="Cada decisão de arquitetura (001 a 012) tem um coordenador especialista; a coordenação geral classifica a demanda, aponta decisões relacionadas e detecta violações de validação em tempo real."
  />
</template>

<script setup>
import CoordenacaoDashboard from '../components/CoordenacaoDashboard.vue'
</script>
