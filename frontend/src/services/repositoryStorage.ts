import type { Message } from '../types'


const STORAGE_KEY = 'codemind-repository-workspace-v1'


// ==========================================================
// TYPES
// ==========================================================

export type HistoryItem = {
  id: string
  question: string
}

export type RepositoryWorkspaceState = {
  repositoryId: string
  repositoryName: string
  messages: Message[]
  question: string
  history: HistoryItem[]
  repositoryReady: boolean
  updatedAt: string
}


// ==========================================================
// LOAD WORKSPACE
// ==========================================================

export function loadRepositoryWorkspace():
  RepositoryWorkspaceState | null {

  try {

    const stored = sessionStorage.getItem(STORAGE_KEY)

    if (!stored) {
      return null
    }

    const data = JSON.parse(stored)

    if (
      !data ||
      typeof data.repositoryId !== 'string' ||
      typeof data.repositoryName !== 'string' ||
      typeof data.question !== 'string' ||
      typeof data.repositoryReady !== 'boolean' ||
      !Array.isArray(data.messages) ||
      !Array.isArray(data.history)
    ) {

      clearRepositoryWorkspace()

      return null
    }

    return data as RepositoryWorkspaceState

  } catch (error) {

    console.warn(
      'Could not restore repository workspace:',
      error,
    )

    clearRepositoryWorkspace()

    return null
  }
}


// ==========================================================
// SAVE WORKSPACE
// ==========================================================

export function saveRepositoryWorkspace(
  state: RepositoryWorkspaceState,
): boolean {

  try {

    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(state),
    )

    return true

  } catch (error) {

    console.warn(
      'Could not save repository workspace:',
      error,
    )

    return false
  }
}


// ==========================================================
// CLEAR WORKSPACE
// ==========================================================

export function clearRepositoryWorkspace(): void {

  try {

    sessionStorage.removeItem(STORAGE_KEY)

  } catch (error) {

    console.warn(
      'Could not clear repository workspace:',
      error,
    )
  }
}