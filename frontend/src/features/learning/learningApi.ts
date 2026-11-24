
const BASE_URL = '/api/learning'

let csrfToken = ''

export type LearningUser = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
}

export type Language = {
  id: string
  name: string
  topics: string[]
  duration_days: number
}

export type Enrollment = {
  id: number
  language: string
  language_name: string
  skill_level: string
  status: string
  current_day: number
  strengths: string[]
  weaknesses: string[]
}

export type Answer = {
  question_id: number
  submitted_answer: string
}

type ApiResponse<T> = {
  success: boolean
  message?: string
  data: T
  errors?: Record<string, unknown>
  detail?: string
}

export class LearningApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(
  endpoint: string,
  method = 'GET',
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  }

  if (method !== 'GET') {
    if (!csrfToken) {
      await initializeCsrf()
    }

    headers['Content-Type'] = 'application/json'
    headers['X-CSRFToken'] = csrfToken
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    method,
    headers,
    credentials: 'same-origin',
    cache: 'no-store',
    body: method !== 'GET'
      ? JSON.stringify(body ?? {})
      : undefined,
  })

  let payload: ApiResponse<T>

  try {
    payload = await response.json()
  } catch {
    throw new LearningApiError(
      response.status === 403
        ? 'Security token expired. Refresh the page and try again.'
        : `Server request failed (${response.status}).`,
      response.status,
    )
  }

  if (!response.ok || payload.success === false) {
    const validationErrors = payload.errors
      ? Object.values(payload.errors)
          .map(value => Array.isArray(value)
            ? value.join(' ')
            : String(value))
          .join(' ')
      : ''

    throw new LearningApiError(
      validationErrors ||
      payload.message ||
      payload.detail ||
      'Request failed. Please try again.',
      response.status,
    )
  }

  return payload.data
}

export async function initializeCsrf() {
  const data = await request<{ csrf_token: string }>(
    '/auth/csrf/',
  )

  csrfToken = data.csrf_token
}

export async function registerUser(data: {
  username: string
  email: string
  first_name: string
  last_name: string
  password: string
  confirm_password: string
}) {
  return request<{ user: LearningUser }>(
    '/auth/register/',
    'POST',
    data,
  )
}

export async function loginUser(
  username: string,
  password: string,
) {
  const data = await request<{
    user: LearningUser
    csrf_token: string
    is_authenticated: boolean
  }>('/auth/login/', 'POST', {
    username,
    password,
  })

  csrfToken = data.csrf_token

  return data.user
}

export async function logoutUser() {
  const data = await request<{
    csrf_token: string
    is_authenticated: boolean
  }>('/auth/logout/', 'POST')

  csrfToken = data.csrf_token
}

export async function getCurrentUser() {
  const data = await request<{
    user: LearningUser
    is_authenticated: boolean
  }>('/auth/me/')

  return data.user
}

export const getLanguages = () =>
  request<Language[]>('/languages/')

export const getEnrollments = () =>
  request<Enrollment[]>('/enrollments/')

export const createEnrollment = (language: string) =>
  request<Enrollment>('/enrollments/', 'POST', { language })

export const getEnrollment = (id: number) =>
  request<Enrollment>(`/enrollments/${id}/`)

// Initial assessment

export const generateInitialAssessment = (id: number) =>
  request(`/enrollments/${id}/assessment/generate/`, 'POST')

export const getInitialAssessment = (id: number) =>
  request(`/enrollments/${id}/assessment/`)

export const startAssessment = (id: number) =>
  request(`/assessments/${id}/start/`, 'POST')

export const saveAnswers = (id: number, answers: Answer[]) =>
  request(`/attempts/${id}/answers/`, 'POST', { answers })

export const submitAssessment = (id: number) =>
  request(`/attempts/${id}/submit/`, 'POST')

export const evaluateAssessment = (id: number) =>
  request(`/attempts/${id}/evaluate/`, 'POST')

export const getAssessmentResult = (id: number) =>
  request(`/attempts/${id}/result/`)

// Roadmap and dashboard

export const generateRoadmap = (id: number) =>
  request(`/enrollments/${id}/roadmap/generate/`, 'POST')

export const getRoadmap = (id: number) =>
  request(`/enrollments/${id}/roadmap/`)

export const getDashboard = (id: number) =>
  request(`/enrollments/${id}/dashboard/`)

export const adaptRoadmap = (id: number) =>
  request(`/enrollments/${id}/roadmap/adapt/`, 'POST')

export const getAdaptationStatus = (id: number) =>
  request(`/enrollments/${id}/roadmap/adaptation/`)

// Daily lessons

export const getLesson = (id: number) =>
  request(`/days/${id}/`)

export const generateLesson = (id: number) =>
  request(`/days/${id}/lesson/generate/`, 'POST')

export const startDay = (id: number) =>
  request(`/days/${id}/start/`, 'POST')

export const completeLesson = (id: number) =>
  request(`/days/${id}/lesson/complete/`, 'POST')

export const completePractical = (id: number) =>
  request(`/days/${id}/practical/complete/`, 'POST')

// Daily assessments

export const generateDailyAssessment = (id: number) =>
  request(`/days/${id}/assessment/generate/`, 'POST')

export const getDailyAssessment = (id: number) =>
  request(`/days/${id}/assessment/`)

export const startDailyAttempt = (id: number) =>
  request(`/days/${id}/assessment/start/`, 'POST')

export const getDailyAttempt = (id: number) =>
  request(`/daily-attempts/${id}/`)

export const saveDailyAnswers = (
  id: number,
  answers: Answer[],
) =>
  request(`/daily-attempts/${id}/answers/`, 'POST', {
    answers,
  })

export const submitDailyAttempt = (id: number) =>
  request(`/daily-attempts/${id}/submit/`, 'POST')

export const evaluateDailyAttempt = (id: number) =>
  request(`/daily-attempts/${id}/evaluate/`, 'POST')

export const getDailyResult = (id: number) =>
  request(`/daily-attempts/${id}/result/`)

// AI job status

export const getAIJobs = (id: number) =>
  request(`/enrollments/${id}/jobs/`)

export const getAIJob = (id: number) =>
  request(`/jobs/${id}/`)
