// ==========================================
// CODEMIND AI - LEARNING STORAGE
// ==========================================

const STORAGE_PREFIX = 'codemind-learning-v1'

// ==========================================
// TYPES
// ==========================================

export type PracticalDraft = {
  completedTasks: number[]
  solutions: Record<number, string>
  updatedAt: string | null
}

export type AssessmentDraft = {
  attemptId: number
  assessmentId: number
  answers: Record<number, string>
  currentIndex: number
  updatedAt: string
}

export type AssessmentType = 'initial' | 'daily'

// ==========================================
// STORAGE KEYS
// ==========================================

function getPracticalStorageKey(
  userId: number,
  dayId: number,
): string {

  return `${STORAGE_PREFIX}:${userId}:day:${dayId}:practical`
}

function getAssessmentStorageKey(
  userId: number,
  type: AssessmentType,
  resourceId: number,
): string {

  return `${STORAGE_PREFIX}:${userId}:${type}:${resourceId}:assessment`
}

// ==========================================
// EMPTY PRACTICAL DRAFT
// ==========================================

function emptyPracticalDraft(): PracticalDraft {

  return {
    completedTasks: [],
    solutions: {},
    updatedAt: null,
  }
}

// ==========================================
// LOAD PRACTICAL DRAFT
// ==========================================

export function loadPracticalDraft(
  userId: number,
  dayId: number,
): PracticalDraft {

  try {

    const saved = localStorage.getItem(
      getPracticalStorageKey(userId, dayId),
    )

    if (!saved) {

      return emptyPracticalDraft()
    }

    const data = JSON.parse(saved)

    if (!data || typeof data !== 'object') {

      return emptyPracticalDraft()
    }

    const completedTasks: number[] =
      Array.isArray(data.completedTasks)
        ? [
            ...new Set<number>(
              data.completedTasks.filter(
                (item: unknown): item is number =>
                  typeof item === 'number' &&
                  Number.isInteger(item) &&
                  item >= 0,
              ),
            ),
          ]
        : []

    const solutions: Record<number, string> = {}

    if (
      data.solutions &&
      typeof data.solutions === 'object' &&
      !Array.isArray(data.solutions)
    ) {

      for (
        const [key, value] of
        Object.entries(data.solutions)
      ) {

        const index = Number(key)

        if (
          Number.isInteger(index) &&
          index >= 0 &&
          typeof value === 'string'
        ) {

          solutions[index] = value
        }
      }
    }

    return {
      completedTasks,
      solutions,
      updatedAt:
        typeof data.updatedAt === 'string'
          ? data.updatedAt
          : null,
    }

  } catch (error) {

    console.warn(
      'Unable to restore practical draft.',
      error,
    )

    return emptyPracticalDraft()
  }
}

// ==========================================
// SAVE PRACTICAL DRAFT
// ==========================================

export function savePracticalDraft(
  userId: number,
  dayId: number,
  completedTasks: number[],
  solutions: Record<number, string>,
): boolean {

  try {

    const draft: PracticalDraft = {
      completedTasks,
      solutions,
      updatedAt: new Date().toISOString(),
    }

    localStorage.setItem(
      getPracticalStorageKey(userId, dayId),
      JSON.stringify(draft),
    )

    return true

  } catch (error) {

    console.warn(
      'Unable to save practical draft.',
      error,
    )

    return false
  }
}

// ==========================================
// CLEAR PRACTICAL DRAFT
// ==========================================

export function clearPracticalDraft(
  userId: number,
  dayId: number,
): boolean {

  try {

    localStorage.removeItem(
      getPracticalStorageKey(userId, dayId),
    )

    return true

  } catch (error) {

    console.warn(
      'Unable to clear practical draft.',
      error,
    )

    return false
  }
}

// ==========================================
// LOAD ASSESSMENT DRAFT
// ==========================================

export function loadAssessmentDraft(
  userId: number,
  type: AssessmentType,
  resourceId: number,
): AssessmentDraft | null {

  try {

    const saved = localStorage.getItem(
      getAssessmentStorageKey(
        userId,
        type,
        resourceId,
      ),
    )

    if (!saved) {

      return null
    }

    const data = JSON.parse(saved)

    if (
      !data ||
      typeof data !== 'object' ||
      !Number.isInteger(data.attemptId) ||
      data.attemptId <= 0 ||
      !Number.isInteger(data.assessmentId) ||
      data.assessmentId <= 0
    ) {

      return null
    }

    const answers: Record<number, string> = {}

    if (
      data.answers &&
      typeof data.answers === 'object' &&
      !Array.isArray(data.answers)
    ) {

      for (
        const [key, value] of
        Object.entries(data.answers)
      ) {

        const questionId = Number(key)

        if (
          Number.isInteger(questionId) &&
          questionId > 0 &&
          typeof value === 'string'
        ) {

          answers[questionId] = value
        }
      }
    }

    return {
      attemptId: data.attemptId,

      assessmentId: data.assessmentId,

      answers,

      currentIndex:
        Number.isInteger(data.currentIndex) &&
        data.currentIndex >= 0
          ? data.currentIndex
          : 0,

      updatedAt:
        typeof data.updatedAt === 'string'
          ? data.updatedAt
          : '',
    }

  } catch (error) {

    console.warn(
      'Unable to restore assessment draft.',
      error,
    )

    return null
  }
}

// ==========================================
// SAVE ASSESSMENT DRAFT
// ==========================================

export function saveAssessmentDraft(
  userId: number,
  type: AssessmentType,
  resourceId: number,
  attemptId: number,
  assessmentId: number,
  answers: Record<number, string>,
  currentIndex = 0,
): boolean {

  try {

    const draft: AssessmentDraft = {
      attemptId,
      assessmentId,
      answers,
      currentIndex,
      updatedAt: new Date().toISOString(),
    }

    localStorage.setItem(
      getAssessmentStorageKey(
        userId,
        type,
        resourceId,
      ),
      JSON.stringify(draft),
    )

    return true

  } catch (error) {

    console.warn(
      'Unable to save assessment draft.',
      error,
    )

    return false
  }
}

// ==========================================
// CLEAR ASSESSMENT DRAFT
// ==========================================

export function clearAssessmentDraft(
  userId: number,
  type: AssessmentType,
  resourceId: number,
): boolean {

  try {

    localStorage.removeItem(
      getAssessmentStorageKey(
        userId,
        type,
        resourceId,
      ),
    )

    return true

  } catch (error) {

    console.warn(
      'Unable to clear assessment draft.',
      error,
    )

    return false
  }
}