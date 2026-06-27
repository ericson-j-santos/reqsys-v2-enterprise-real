import { api } from './api'

export async function carregarRuntimeDashboard() {
  const { data } = await api.get('/runtime-validator/dashboard')
  return data.data
}

export async function validarWorkflow(payload) {
  const { data } = await api.post('/runtime-validator/workflows/validate', payload)
  return data.data
}

export async function solicitarRemediacao(payload) {
  const { data } = await api.post('/runtime-validator/remediations', payload)
  return data.data
}
