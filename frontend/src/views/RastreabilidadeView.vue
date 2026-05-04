<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>Matriz de Rastreabilidade</h1>
        <p class="muted trace-subtitle">
          Visualize o vínculo entre requisito, história, gestão operacional e entrega técnica.
        </p>
      </div>
      <div class="header-actions">
        <v-tooltip text="Visão de demonstração da cadeia ponta a ponta" location="top">
          <template #activator="{ props }">
            <v-chip v-bind="props" color="amber" variant="tonal">Visão guiada</v-chip>
          </template>
        </v-tooltip>
      </div>
    </div>

    <v-alert type="info" variant="tonal" class="mb-4">
      Cada linha mostra o encadeamento completo entre necessidade, implementação e evidência técnica.
    </v-alert>

    <v-card class="table-card">
      <v-card-title class="py-3 px-4">Encadeamento de artefatos</v-card-title>
      <v-divider />
      <v-table>
        <thead>
          <tr>
            <th>Requisito</th>
            <th>História</th>
            <th>Redmine</th>
            <th>Planner</th>
            <th>Commit</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in linhas" :key="r.req">
            <td>
              <strong>{{ r.req }}</strong>
              <div class="muted text-caption">Origem formal</div>
            </td>
            <td>{{ r.historia }}</td>
            <td>
              <v-tooltip text="Item sincronizado com a gestão operacional no Redmine" location="top">
                <template #activator="{ props }">
                  <span v-bind="props">{{ r.redmine }}</span>
                </template>
              </v-tooltip>
            </td>
            <td>{{ r.planner }}</td>
            <td>
              <v-tooltip text="Referência do commit que materializou a entrega" location="top">
                <template #activator="{ props }">
                  <code v-bind="props">{{ r.commit }}</code>
                </template>
              </v-tooltip>
            </td>
            <td>
              <v-tooltip text="Status consolidado de rastreabilidade" location="top">
                <template #activator="{ props }">
                  <v-chip v-bind="props" size="small" color="green">{{ r.status }}</v-chip>
                </template>
              </v-tooltip>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </section>
</template>

<script setup>
const linhas = [{ req: 'REQ-0001', historia: 'US-0001', redmine: '#42', planner: 'PLN-104', commit: 'abc1234', status: 'rastreado' }]
</script>

<style scoped>
.trace-subtitle {
  max-width: 58ch;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
