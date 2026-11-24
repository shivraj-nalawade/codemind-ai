type PracticalDraft = {
  completedTasks: number[]
  solutions: Record<number, string>
  updatedAt: string | null
}

const STORAGE_PREFIX = 'codemind-learning-v1'

function getStorageKey(
  userId: number,
  dayId: number,
): string {
  return `${STORAGE_PREFIX}:${userId}:day:${dayId}:practical`
}

function emptyDraft(): PracticalDraft {
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
    const key = getStorageKey(userId, dayId)

    const saved = localStorage.getItem(key)

    if (!saved) {
      return emptyDraft()
    }

    const data = JSON.parse(saved)

    if (!data || typeof data !== 'object') {
      return emptyDraft()
    }

    const completedTasks: number[] =
      Array.isArray(data.completedTasks)
        ? [...new Set<number>(
            data.completedTasks.filter(
              (item: unknown): item is number =>
                typeof item === 'number' &&
                Number.isInteger(item) &&
                item >= 0,
            ),
          )]
        : []

    const solutions: Record<number, string> = {}

    if (
      data.solutions &&
      typeof data.solutions === 'object' &&
      !Array.isArray(data.solutions)
    ) {
      for (const [key, value] of Object.entries(
        data.solutions,
      )) {
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

    return emptyDraft()
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
    const key = getStorageKey(userId, dayId)

    const draft: PracticalDraft = {
      completedTasks,
      solutions,
      updatedAt: new Date().toISOString(),
    }

    localStorage.setItem(
      key,
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
// DELETE PRACTICAL DRAFT
// ==========================================

export function clearPracticalDraft(
  userId: number,
  dayId: number,
): boolean {

  try {
    localStorage.removeItem(
      getStorageKey(userId, dayId),
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