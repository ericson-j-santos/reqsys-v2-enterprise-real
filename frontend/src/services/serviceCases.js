const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const SHA256_RE = /^[a-f0-9]{64}$/

export function validarServiceCaseId(value) {
  const normalized = String(value || '').trim()
  if (!UUID_RE.test(normalized)) throw new Error('Informe um identificador de caso válido.')
  return normalized
}

function eventId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  throw new Error('O navegador não oferece geração segura de identificador para esta ação.')
}

export async function carregarServiceCase(apiClient, rawCaseId) {
  const caseId = validarServiceCaseId(rawCaseId)
  const [caseResponse, operationsResponse] = await Promise.all([
    apiClient.get(`/v1/service-cases/${caseId}`),
    apiClient.get(`/v1/service-cases/${caseId}/operations`),
  ])
  const caseData = caseResponse?.data?.data
  const operations = operationsResponse?.data?.data
  if (!caseData || caseData.case_id !== caseId) {
    throw new Error('A leitura do caso retornou uma identidade divergente.')
  }
  if (!operations || operations.case_id !== caseId) {
    throw new Error('A leitura operacional retornou uma identidade divergente.')
  }
  return { caseData, operations }
}

export async function executarTransicaoServiceCase(
  apiClient,
  caseData,
  targetState,
  { evidenceUri = '', evidenceSha256 = '' } = {},
) {
  if (!caseData?.case_id || !Number.isInteger(caseData?.version)) {
    throw new Error('O estado atual do caso não é suficiente para executar a ação.')
  }
  const allowed = Array.isArray(caseData.allowed_transitions) ? caseData.allowed_transitions : []
  if (!allowed.includes(targetState)) {
    throw new Error('A ação não está permitida pelo estado persistido atual.')
  }

  const payload = {
    target_state: targetState,
    expected_version: caseData.version,
    event_id: eventId(),
  }
  if (targetState === 'RESOLVED') {
    const uri = String(evidenceUri || '').trim()
    const sha = String(evidenceSha256 || '').trim().toLowerCase()
    if (!uri || !SHA256_RE.test(sha)) {
      throw new Error('Resolver o caso exige URI de evidência e SHA-256 válido.')
    }
    payload.evidence_uri = uri
    payload.evidence_sha256 = sha
  }

  const mutation = await apiClient.post(`/v1/service-cases/${caseData.case_id}/transitions`, payload)
  const duplicate = Boolean(mutation?.data?.data?.duplicate)

  // Leitura independente do POST: sucesso visual só existe se o GET observar o efeito persistido.
  const refreshed = await carregarServiceCase(apiClient, caseData.case_id)
  if (refreshed.caseData.state !== targetState) {
    throw new Error(
      `A ação respondeu sem erro, mas a leitura persistida permaneceu em ${refreshed.caseData.state}.`,
    )
  }
  return { ...refreshed, duplicate }
}
