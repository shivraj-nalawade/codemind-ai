import type { ApiError, Source, UploadResult } from '../types'

const API = '/api/repositories'

const CSRF_API = '/api/learning/auth/csrf/'


// ==========================================================
// TYPES
// ==========================================================

export type RepositoryStatus = {
  repository_id: string
  parsed: boolean
  indexed: boolean
  ready: boolean
}


// ==========================================================
// RESPONSE HANDLING
// ==========================================================

async function readResponse<T>(
  response: Response,
): Promise<T> {

  const data = await response.json().catch(
    () => ({} as ApiError),
  )

  if (!response.ok) {

    const apiError = data as ApiError

    const message = Array.isArray(apiError.error)
      ? apiError.error.join(', ')
      : apiError.error ||
        `Request failed (${response.status})`

    throw new Error(message)
  }

  return data as T
}


// ==========================================================
// CSRF TOKEN
// ==========================================================

async function getCsrfToken(): Promise<string> {

  const response = await fetch(CSRF_API, {
    method: 'GET',
    credentials: 'same-origin',
    cache: 'no-store',
    headers: {
      Accept: 'application/json',
    },
  })

  const result = await readResponse<{
    data: {
      csrf_token: string
    }
  }>(response)

  const token = result.data?.csrf_token

  if (!token) {
    throw new Error(
      'Could not initialize repository security.',
    )
  }

  return token
}


// ==========================================================
// SECURE POST REQUEST
// ==========================================================

async function securePost<T>(
  endpoint: string,
  body?: FormData | string,
): Promise<T> {

  const csrfToken = await getCsrfToken()

  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-CSRFToken': csrfToken,
  }

  if (typeof body === 'string') {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    cache: 'no-store',
    headers,
    body,
  })

  return readResponse<T>(response)
}


// ==========================================================
// UPLOAD REPOSITORY
// ==========================================================

export async function uploadRepository(
  file: File,
): Promise<UploadResult> {

  const form = new FormData()

  form.append('file', file)

  return securePost<UploadResult>(
    `${API}/upload/`,
    form,
  )
}


// ==========================================================
// PARSE REPOSITORY
// ==========================================================

export async function parseRepository(
  repositoryId: string,
): Promise<void> {

  await securePost(
    `${API}/${repositoryId}/parse/`,
  )
}


// ==========================================================
// BUILD SEMANTIC INDEX
// ==========================================================

export async function buildSemanticIndex(
  repositoryId: string,
): Promise<void> {

  await securePost(
    `${API}/${repositoryId}/semantic-index/`,
  )
}


// ==========================================================
// ASK REPOSITORY
// ==========================================================

export async function askRepository(
  repositoryId: string,
  question: string,
): Promise<{
  answer: string
  sources: Source[]
}> {

  return securePost<{
    answer: string
    sources: Source[]
  }>(
    `${API}/${repositoryId}/ask/`,
    JSON.stringify({ question }),
  )
}


// ==========================================================
// CHECK REPOSITORY STATUS
// ==========================================================

export async function getRepositoryStatus(
  repositoryId: string,
): Promise<RepositoryStatus | null> {

  const response = await fetch(
    `${API}/${repositoryId}/status/`,
    {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
      },
    },
  )

  // Repository is missing or the session no longer has access.
  if (response.status === 404) {
    return null
  }

  return readResponse<RepositoryStatus>(response)
}