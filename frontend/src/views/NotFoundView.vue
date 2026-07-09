<template>
  <main class="not-found-page" data-testid="route-not-found">
    <v-card class="not-found-card" elevation="0">
      <v-chip color="warning" variant="tonal" class="mb-4">Navegação assistida</v-chip>
      <h1>Rota não encontrada</h1>
      <p>
        A página solicitada não faz parte do catálogo operacional do ReqSys. Use os atalhos abaixo
        para voltar a uma tela estável e reduzir erro percebido no ambiente publicado.
      </p>
      <div class="not-found-actions">
        <v-btn color="primary" to="/" prepend-icon="mdi-view-dashboard">Ir para o dashboard</v-btn>
        <v-btn variant="tonal" to="/monitoramento-operacional" prepend-icon="mdi-pulse">Monitoramento</v-btn>
        <v-btn variant="text" to="/login" prepend-icon="mdi-login">Login</v-btn>
      </div>
    </v-card>
  </main>
</template>

<style scoped>
.not-found-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: clamp(24px, 5vw, 56px);
  background: radial-gradient(circle at top left, rgba(251, 191, 36, 0.14), transparent 34%), #070b16;
}

.not-found-card {
  width: min(100%, 720px);
  padding: clamp(24px, 4vw, 40px);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 28px;
  background: rgba(15, 23, 42, 0.94);
  color: #e5e7eb;
}

.not-found-card h1 {
  margin: 0 0 12px;
  font-size: clamp(2rem, 5vw, 3.25rem);
  line-height: 1;
}

.not-found-card p {
  max-width: 60ch;
  margin-bottom: 24px;
  color: #cbd5e1;
}

.not-found-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
</style>
