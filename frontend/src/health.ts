export type Health = {
  status: 'ready'
  project_id: 'GOV-CS-028'
  phase: 12
  required_dependencies: Record<string, string>
  optional_services: Record<string, string>
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
export const healthUrl = `${baseUrl}/health/ready`

export async function fetchHealth(signal: AbortSignal): Promise<{ health: Health; requestId: string }> {
  const response = await fetch(healthUrl, { signal, cache: 'no-store' })
  if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}`)
  const data: unknown = await response.json()
  if (typeof data !== 'object' || data === null) throw new Error('Invalid health response')
  const value = data as Partial<Health>
  if (value.status !== 'ready' || value.project_id !== 'GOV-CS-028' || value.phase !== 12
      || !isStringRecord(value.required_dependencies) || !isStringRecord(value.optional_services)) {
    throw new Error('Backend returned an unexpected health response')
  }
  return { health: value as Health, requestId: response.headers.get('X-Request-ID') || 'Unavailable' }
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    && Object.values(value).every((item) => typeof item === 'string')
}
