import type { ApiError, Source, UploadResult } from '../types'

const API = '/api/repositories'

async function readResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({} as ApiError))

  if (!response.ok) {
    const apiError = data as ApiError
    const message = Array.isArray(apiError.error)
      ? apiError.error.join(', ')
      : apiError.error || `Request failed (${response.status})`

    throw new Error(message)
  }

  return data as T
}

export async function uploadRepository(file: File): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)

  return readResponse<UploadResult>(
    await fetch(`${API}/upload/`, {
      method: 'POST',
      body: form,
    }),
  )
}

export async function parseRepository(repositoryId: string): Promise<void> {
  await readResponse(
    await fetch(`${API}/${repositoryId}/parse/`),
  )
}

export async function buildSemanticIndex(
  repositoryId: string,
): Promise<void> {
  await readResponse(
    await fetch(`${API}/${repositoryId}/semantic-index/`, {
      method: 'POST',
    }),
  )
}

export async function askRepository(
  repositoryId: string,
  question: string,
): Promise<{ answer: string; sources: Source[] }> {
  return readResponse<{ answer: string; sources: Source[] }>(
    await fetch(`${API}/${repositoryId}/ask/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    }),
  )
}