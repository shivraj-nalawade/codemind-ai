import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import {
  getLesson,
  generateLesson,
  startDay,
  completeLesson,
  completePractical,
} from './learningApi'

import {
  loadPracticalDraft,
  savePracticalDraft,
} from './learningStorage'

import DailyAssessment from './DailyAssessment'

// ==========================================
// TYPES
// ==========================================

type LessonTab = 'lesson' | 'practice' | 'assessment'

type CodeExample = {
  title: string
  description: string
  language: string
  code: string
  expected_output: string
  explanation: string
}

type PracticalTask = {
  title: string
  description: string
  difficulty: string
  requirements: string[]
  sample_input: string
  expected_output: string
  hints: string[]
}

type Lesson = {
  learning_day_id: number
  day_number: number
  title: string
  topic: string
  difficulty: string
  estimated_minutes: number
  learning_objectives: string[]
  explanation: string
  code_examples: CodeExample[]
  practical_tasks: PracticalTask[]
  is_content_generated?: boolean
  content_generated?: boolean
  status: string
  lesson_completed: boolean
  practical_completed: boolean
  assessment_completed: boolean

  progress?: {
    status: string
    lesson_completed: boolean
    practical_completed: boolean
    assessment_completed: boolean
  }
}

type Props = {
  userId: number
  dayId: number
  onBack: () => void
  onComplete: () => void
}

// ==========================================
// MARKDOWN RENDERER
// ==========================================

function LessonMarkdown({
  content,
  className = '',
}: {
  content: string
  className?: string
}) {
  return (
    <div className={`learning-markdown ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

// ==========================================
// DAILY LESSON COMPONENT
// ==========================================

export default function DailyLesson({
  userId,
  dayId,
  onBack,
  onComplete,
}: Props) {

  const location = useLocation()
  const navigate = useNavigate()

  const [lesson, setLesson] =
    useState<Lesson | null>(null)

  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  // ==========================================
  // RESTORE SAVED PRACTICAL DRAFT
  // ==========================================

  const [initialDraft] = useState(() =>
    loadPracticalDraft(userId, dayId),
  )

  const [completedTasks, setCompletedTasks] =
    useState<number[]>(initialDraft.completedTasks)

  const [solutions, setSolutions] =
    useState<Record<number, string>>(
      initialDraft.solutions,
    )

  const [draftSaved, setDraftSaved] = useState(false)

  const [copied, setCopied] =
    useState<number | null>(null)

  // ==========================================
  // AUTOMATIC PRACTICAL DRAFT SAVING
  // ==========================================

  useEffect(() => {

    const saved = savePracticalDraft(
      userId,
      dayId,
      completedTasks,
      solutions,
    )

    setDraftSaved(saved)

  }, [
    userId,
    dayId,
    completedTasks,
    solutions,
  ])

  // ==========================================
  // URL-BASED TAB NAVIGATION
  // ==========================================

  const currentPath = location.pathname.replace(
    /\/+$/,
    '',
  )

  const currentTab = currentPath
    .split('/')
    .filter(Boolean)
    .pop()

  const requestedTab: LessonTab =
    currentTab === 'practical'
      ? 'practice'
      : currentTab === 'assessment'
        ? 'assessment'
        : 'lesson'

  const basePath = currentPath.replace(
    /\/(lesson|practical|assessment)$/,
    '',
  )

  function getTabPath(nextTab: LessonTab) {

    const urlTab =
      nextTab === 'practice'
        ? 'practical'
        : nextTab

    return `${basePath}/${urlTab}`
  }

  function setTab(nextTab: LessonTab) {

    const nextPath = getTabPath(nextTab)

    if (nextPath !== currentPath) {
      navigate(nextPath)
    }

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  // ==========================================
  // LEARNING PROGRESS
  // ==========================================

  const progress = lesson?.progress ?? lesson

  const contentGenerated = Boolean(
    lesson?.is_content_generated ||
    lesson?.content_generated ||
    lesson?.explanation,
  )

  // Prevent rendering inaccessible tabs.

  let tab: LessonTab = requestedTab

  if (lesson) {

    if (
      progress?.status === 'locked' ||
      progress?.status === 'unlocked' ||
      !contentGenerated ||
      !progress?.lesson_completed
    ) {

      tab = 'lesson'

    } else if (
      requestedTab === 'assessment' &&
      !progress?.practical_completed
    ) {

      tab = 'practice'

    }
  }

  // ==========================================
  // PROTECT URL-BASED NAVIGATION
  // ==========================================

  useEffect(() => {

    if (!lesson || loading || busy) return

    const allowedUrlTab =
      tab === 'practice'
        ? 'practical'
        : tab

    const allowedPath =
      `${basePath}/${allowedUrlTab}`

    if (currentPath !== allowedPath) {

      navigate(allowedPath, {
        replace: true,
      })

    }

  }, [
    lesson,
    loading,
    busy,
    tab,
    basePath,
    currentPath,
    navigate,
  ])

  // ==========================================
  // LOAD LESSON
  // ==========================================

  async function refreshLesson() {

    const data = await getLesson(dayId) as Lesson

    setLesson(data)

    return data
  }

  async function loadLesson() {

    setLoading(true)
    setError('')

    try {

      await refreshLesson()

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Unable to load lesson.',
      )

    } finally {

      setLoading(false)

    }
  }

  useEffect(() => {

    let active = true

    setLesson(null)
    setCopied(null)
    setLoading(true)
    setError('')

    // Do not reset practical drafts here.
    // They are restored from localStorage.

    async function initializeLesson() {

      try {

        const data = await getLesson(dayId) as Lesson

        if (active) {
          setLesson(data)
        }

      } catch (err) {

        if (active) {

          setError(
            err instanceof Error
              ? err.message
              : 'Unable to load lesson.',
          )

        }

      } finally {

        if (active) {
          setLoading(false)
        }

      }
    }

    void initializeLesson()

    return () => {
      active = false
    }

  }, [dayId])

  // ==========================================
  // COMMON ACTION HANDLER
  // ==========================================

  async function runAction(
    action: () => Promise<unknown>,
    message: string,
    nextTab?: LessonTab,
  ) {

    if (busy) return

    setBusy(true)
    setError('')
    setStatus(message)

    try {

      await action()

      // Refresh official backend progress.

      await refreshLesson()

      if (nextTab) {
        setTab(nextTab)
      }

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Operation failed. Please retry.',
      )

    } finally {

      setBusy(false)
      setStatus('')

    }
  }

  // ==========================================
  // GENERATE AND START LESSON
  // ==========================================

  async function prepareLesson() {

    await runAction(

      async () => {

        if (!contentGenerated) {
          await generateLesson(dayId)
        }

        await startDay(dayId)

      },

      'Preparing your personalized lesson...',
      'lesson',

    )
  }

  // ==========================================
  // COMPLETE LESSON
  // ==========================================

  async function finishLesson() {

    await runAction(
      () => completeLesson(dayId),
      'Saving lesson progress...',
      'practice',
    )
  }

  // ==========================================
  // COMPLETE PRACTICAL
  // ==========================================

  async function finishPractice() {

    await runAction(
      () => completePractical(dayId),
      'Saving practical progress...',
      'assessment',
    )
  }

  // ==========================================
  // PRACTICAL TASK HANDLER
  // ==========================================

  function toggleTask(index: number) {

    setCompletedTasks(previous =>
      previous.includes(index)
        ? previous.filter(item => item !== index)
        : [...previous, index],
    )
  }

  // ==========================================
  // PRACTICAL SOLUTION HANDLER
  // ==========================================

  function updateSolution(
    index: number,
    value: string,
  ) {

    setSolutions(previous => ({
      ...previous,
      [index]: value,
    }))
  }

  // ==========================================
  // COPY CODE
  // ==========================================

  async function copyCode(
    code: string,
    index: number,
  ) {

    try {

      await navigator.clipboard.writeText(code)

      setCopied(index)

    } catch {

      setError('Unable to copy code.')

    }
  }

  // ==========================================
  // LOADING SCREEN
  // ==========================================

  if (loading) {

    return (
      <div className="flex items-center gap-3 p-8">

        <div className="h-6 w-6 animate-spin
          rounded-full border-2 border-orange-500
          border-t-transparent" />

        <p className="text-orange-400">
          Loading lesson...
        </p>

      </div>
    )
  }

  // ==========================================
  // ERROR SCREEN
  // ==========================================

  if (!lesson) {

    return (
      <div className="p-8">

        <p className="text-red-400">
          {error}
        </p>

        <button
          onClick={() => void loadLesson()}
          className="learning-primary mt-5"
        >
          Retry
        </button>

        <button
          onClick={onBack}
          className="ml-5 text-orange-400"
        >
          Back to roadmap
        </button>

      </div>
    )
  }

  const tasks = lesson.practical_tasks ?? []
  const examples = lesson.code_examples ?? []

  // Count only valid task indexes.

  const validCompletedTasks = completedTasks.filter(
    index => index >= 0 && index < tasks.length,
  )

  const completedTaskCount =
    progress?.practical_completed
      ? tasks.length
      : validCompletedTasks.length

  const practicalPercentage =
    progress?.practical_completed
      ? 100
      : tasks.length > 0
        ? completedTaskCount / tasks.length * 100
        : 0

  // ==========================================
  // MAIN LESSON INTERFACE
  // ==========================================

  return (

    <section className="mx-auto max-w-6xl space-y-6 py-6">

      {/* BACK BUTTON */}

      <button
        disabled={busy}
        onClick={onBack}
        className="text-sm text-orange-400
          hover:text-orange-300 disabled:opacity-50"
      >
        ← Back to roadmap
      </button>

      {/* ERROR MESSAGE */}

      {error && (

        <div
          role="alert"
          className="rounded-xl border border-red-900
            bg-red-950/40 p-4 text-red-300"
        >

          {error}

        </div>

      )}

      {/* PROCESSING STATUS */}

      {busy && (

        <div
          role="status"
          className="flex items-center gap-4 rounded-xl
            bg-orange-500/10 p-5 text-orange-400"
        >

          <div className="h-6 w-6 animate-spin
            rounded-full border-2 border-orange-500
            border-t-transparent" />

          <div>

            <p>{status}</p>

            <p className="mt-1 text-sm text-neutral-400">
              Please wait while your request is processed.
            </p>

          </div>

        </div>

      )}

      {/* LESSON HEADER */}

      <div className="rounded-2xl border border-neutral-800
        bg-[#191919] p-7">

        <p className="text-sm font-bold uppercase
          tracking-widest text-orange-500">

          Day {lesson.day_number} · Personalized Learning

        </p>

        <h1 className="mt-3 text-3xl font-bold">

          {lesson.title}

        </h1>

        <div className="mt-4 flex flex-wrap gap-3
          text-sm text-neutral-400">

          <span>{lesson.topic}</span>

          <span>·</span>

          <span className="capitalize">
            {lesson.difficulty}
          </span>

          <span>·</span>

          <span>
            {lesson.estimated_minutes} minutes
          </span>

        </div>

        {/* LEARNING OBJECTIVES */}

        <h3 className="mb-3 mt-6 font-semibold">
          Learning Objectives
        </h3>

        <div className="learning-markdown">

          <ul>

            {(lesson.learning_objectives ?? []).map(
              (objective, index) => (

                <li key={index}>

                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {objective}
                  </ReactMarkdown>

                </li>

              ),
            )}

          </ul>

        </div>

      </div>

      {/* LOCKED LESSON */}

      {progress?.status === 'locked' ? (

        <div className="rounded-xl bg-neutral-800 p-6">

          Complete the previous day to unlock this lesson.

        </div>

      ) : !contentGenerated ||
        progress?.status === 'unlocked' ? (

        /* GENERATE PERSONALIZED LESSON */

        <div className="rounded-2xl border border-neutral-800
          bg-[#191919] p-8 text-center">

          <h2 className="text-2xl font-bold">

            Your Personalized Lesson

          </h2>

          <p className="mx-auto mt-4 max-w-xl
            text-neutral-400">

            AI will prepare explanations, code examples and
            practical exercises based on your assessment
            performance and learning objectives.

          </p>

          <button
            disabled={busy}
            onClick={() => void prepareLesson()}
            className="learning-primary mt-6"
          >

            {busy ? 'Preparing...' : 'Start Learning'}

          </button>

        </div>

      ) : (

        <>

          {/* LESSON NAVIGATION TABS */}

          <div className="grid grid-cols-3 gap-2
            rounded-xl bg-[#191919] p-2">

            <button
              disabled={busy}
              onClick={() => setTab('lesson')}
              className={`rounded-lg p-3 text-sm ${
                tab === 'lesson'
                  ? 'bg-orange-500 font-semibold text-black'
                  : 'text-neutral-300'
              }`}
            >

              {progress?.lesson_completed ? '✓ ' : ''}
              1. Lesson

            </button>

            <button
              disabled={busy || !progress?.lesson_completed}
              onClick={() => setTab('practice')}
              className={`rounded-lg p-3 text-sm
                disabled:opacity-40 ${
                  tab === 'practice'
                    ? 'bg-orange-500 font-semibold text-black'
                    : 'text-neutral-300'
                }`}
            >

              {progress?.practical_completed ? '✓ ' : ''}
              2. Practical

            </button>

            <button
              disabled={
                busy ||
                !progress?.lesson_completed ||
                !progress?.practical_completed
              }
              onClick={() => setTab('assessment')}
              className={`rounded-lg p-3 text-sm
                disabled:opacity-40 ${
                  tab === 'assessment'
                    ? 'bg-orange-500 font-semibold text-black'
                    : 'text-neutral-300'
                }`}
            >

              {progress?.assessment_completed ? '✓ ' : ''}
              3. Assessment

            </button>

          </div>

          {/* ==========================================
              TAB 1: LESSON EXPLANATION
              ========================================== */}

          {tab === 'lesson' && (

            <div className="space-y-6">

              <article className="rounded-2xl border
                border-neutral-800 bg-[#191919] p-7">

                <h2 className="mb-6 text-2xl font-bold">

                  Understanding the Topic

                </h2>

                <LessonMarkdown
                  content={lesson.explanation}
                />

              </article>

              {/* CODE EXAMPLES */}

              <h2 className="text-2xl font-bold">

                Code Examples

              </h2>

              {examples.map((example, index) => (

                <article
                  key={index}
                  className="overflow-hidden rounded-2xl
                    border border-neutral-800 bg-[#191919]"
                >

                  <div className="p-6">

                    <h3 className="text-xl font-bold">

                      Example {index + 1}: {example.title}

                    </h3>

                    <LessonMarkdown
                      content={example.description}
                      className="mt-3"
                    />

                  </div>

                  {/* CODE BLOCK HEADER */}

                  <div className="flex items-center
                    justify-between bg-neutral-800 px-5 py-3">

                    <span className="text-sm text-orange-400">

                      {example.language}

                    </span>

                    <button
                      onClick={() => void copyCode(
                        example.code,
                        index,
                      )}
                      className="text-sm text-neutral-300
                        hover:text-orange-400"
                    >

                      {copied === index
                        ? '✓ Copied!'
                        : 'Copy code'}

                    </button>

                  </div>

                  {/* CODE BLOCK */}

                  <pre className="overflow-x-auto
                    bg-[#0d0d0d] p-6 text-sm
                    leading-relaxed text-green-300">

                    <code>{example.code}</code>

                  </pre>

                  {/* EXPECTED OUTPUT */}

                  <div className="space-y-4 p-6">

                    <h4 className="font-semibold">

                      Expected Output

                    </h4>

                    <pre className="overflow-x-auto
                      rounded-lg bg-neutral-900 p-4
                      text-sm text-orange-300">

                      {example.expected_output}

                    </pre>

                    <h4 className="font-semibold">

                      Code Explanation

                    </h4>

                    <LessonMarkdown
                      content={example.explanation}
                    />

                  </div>

                </article>

              ))}

              {/* COMPLETE LESSON BUTTON */}

              <button
                disabled={busy}
                onClick={() => {

                  if (progress?.lesson_completed) {

                    setTab('practice')

                  } else {

                    void finishLesson()

                  }

                }}
                className="learning-primary w-full"
              >

                {progress?.lesson_completed
                  ? 'Continue to Practical Tasks'
                  : 'Mark Lesson Complete & Continue'}

              </button>

            </div>

          )}

          {/* ==========================================
              TAB 2: PRACTICAL EXERCISES
              ========================================== */}

          {tab === 'practice' && (

            <div className="space-y-6">

              <div className="rounded-xl
                bg-orange-500/10 p-5">

                <h2 className="text-xl font-bold
                  text-orange-400">

                  Practical Coding Exercises

                </h2>

                <p className="mt-2 text-sm text-neutral-300">

                  Practice independently using your IDE.
                  Mark each task complete after testing it.
                  This section uses self-reported completion;
                  code is not automatically executed.

                </p>

                {/* AUTOMATIC DRAFT SAVING INDICATOR */}

                <div className="mt-4 flex flex-wrap items-center
                  justify-between gap-3 rounded-lg
                  border border-neutral-800 bg-[#191919] p-3">

                  <div>

                    <p className="text-sm font-medium
                      text-neutral-300">

                      Automatic Draft Saving

                    </p>

                    <p className="mt-1 text-xs
                      text-neutral-400">

                      Your code and task checkboxes are saved
                      automatically in this browser.

                    </p>

                  </div>

                  <span
                    role="status"
                    className={`text-xs font-medium ${
                      draftSaved
                        ? 'text-green-400'
                        : 'text-yellow-400'
                    }`}
                  >

                    {draftSaved
                      ? '✓ Draft saved locally'
                      : '⚠ Local saving unavailable'}

                  </span>

                </div>

                <p className="mt-3 text-xs text-neutral-400">

                  Drafts are specific to your account and
                  learning day. They are not synchronized
                  across browsers or devices.

                </p>

              </div>

              {/* PRACTICAL PROGRESS */}

              <div className="rounded-xl border
                border-neutral-800 bg-[#191919] p-5">

                <div className="mb-3 flex items-center
                  justify-between">

                  <span className="font-semibold">

                    Practical Progress

                  </span>

                  <span className="text-orange-400">

                    {completedTaskCount}
                    {' / '}
                    {tasks.length} completed

                  </span>

                </div>

                <div className="h-2 overflow-hidden
                  rounded-full bg-neutral-800">

                  <div
                    className="h-full rounded-full
                      bg-orange-500 transition-all"
                    style={{
                      width: `${practicalPercentage}%`,
                    }}
                  />

                </div>

              </div>

              {/* PRACTICAL TASKS */}

              {tasks.map((task, index) => (

                <article
                  key={index}
                  className="rounded-2xl border
                    border-neutral-800 bg-[#191919] p-6"
                >

                  <div className="flex flex-wrap
                    justify-between gap-3">

                    <h3 className="text-xl font-bold">

                      Task {index + 1}: {task.title}

                    </h3>

                    <span className="rounded-md
                      bg-neutral-800 px-3 py-1 text-sm
                      capitalize text-orange-400">

                      {task.difficulty}

                    </span>

                  </div>

                  {/* TASK DESCRIPTION */}

                  <LessonMarkdown
                    content={task.description}
                    className="mt-4"
                  />

                  {/* TASK REQUIREMENTS */}

                  <h4 className="mb-2 mt-5 font-semibold">

                    Requirements

                  </h4>

                  <div className="learning-markdown">

                    <ul>

                      {(task.requirements ?? []).map(
                        (item, i) => (

                          <li key={i}>

                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                            >

                              {item}

                            </ReactMarkdown>

                          </li>

                        ),
                      )}

                    </ul>

                  </div>

                  {/* SAMPLE INPUT AND OUTPUT */}

                  <div className="my-5 grid gap-4
                    md:grid-cols-2">

                    <div className="rounded-lg
                      bg-neutral-900 p-4">

                      <p className="mb-3 text-sm
                        text-neutral-400">

                        Sample Input

                      </p>

                      <pre className="overflow-x-auto
                        whitespace-pre-wrap text-sm">

                        {task.sample_input}

                      </pre>

                    </div>

                    <div className="rounded-lg
                      bg-neutral-900 p-4">

                      <p className="mb-3 text-sm
                        text-neutral-400">

                        Expected Output

                      </p>

                      <pre className="overflow-x-auto
                        whitespace-pre-wrap text-sm
                        text-green-300">

                        {task.expected_output}

                      </pre>

                    </div>

                  </div>

                  {/* CODE EDITOR HEADER */}

                  <div className="mb-2 flex flex-wrap
                    items-center justify-between gap-2">

                    <h4 className="font-semibold">

                      Your Solution

                    </h4>

                    <span className="text-xs text-neutral-500">

                      {(solutions[index] ?? '').length}
                      {' characters'}

                    </span>

                  </div>

                  {/* CODE WRITING AREA */}

                  <textarea
                    rows={10}
                    spellCheck={false}
                    value={solutions[index] ?? ''}
                    onChange={event =>
                      updateSolution(
                        index,
                        event.target.value,
                      )
                    }
                    placeholder="Write your solution here..."
                    className="learning-input font-mono"
                  />

                  {/* CODE EDITOR FOOTER */}

                  <div className="mt-2 flex flex-wrap
                    items-center justify-between gap-2">

                    <span className={`text-xs ${
                      draftSaved
                        ? 'text-green-400'
                        : 'text-yellow-400'
                    }`}>

                      {draftSaved
                        ? '✓ Autosave enabled'
                        : 'Local saving unavailable'}

                    </span>

                    <button
                      type="button"
                      disabled={!solutions[index]}
                      onClick={() => void copyCode(
                        solutions[index] ?? '',
                        examples.length + index,
                      )}
                      className="text-xs text-orange-400
                        hover:text-orange-300
                        disabled:opacity-40"
                    >

                      {copied === examples.length + index
                        ? '✓ Copied!'
                        : 'Copy solution'}

                    </button>

                  </div>

                  {/* HINTS */}

                  <details className="my-4 rounded-lg
                    bg-neutral-800 p-4">

                    <summary className="cursor-pointer
                      font-medium text-orange-400">

                      Show Hints

                    </summary>

                    <div className="learning-markdown mt-3">

                      <ul>

                        {(task.hints ?? []).map(
                          (hint, i) => (

                            <li key={i}>

                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                              >

                                {hint}

                              </ReactMarkdown>

                            </li>

                          ),
                        )}

                      </ul>

                    </div>

                  </details>

                  {/* TASK COMPLETION CHECKBOX */}

                  <label className="flex cursor-pointer
                    items-center gap-3 text-sm">

                    <input
                      type="checkbox"
                      disabled={
                        busy ||
                        progress?.practical_completed
                      }
                      checked={
                        Boolean(progress?.practical_completed) ||
                        completedTasks.includes(index)
                      }
                      onChange={() => toggleTask(index)}
                      className="h-5 w-5 accent-orange-500"
                    />

                    I have completed and tested this exercise.

                  </label>

                  {/* TASK COMPLETION STATUS */}

                  {(progress?.practical_completed ||
                    completedTasks.includes(index)) && (

                    <div className="mt-4 rounded-lg
                      border border-green-900
                      bg-green-950/20 p-3">

                      <p className="text-sm text-green-400">

                        ✓ Exercise marked as completed

                      </p>

                    </div>

                  )}

                </article>

              ))}

              {/* COMPLETE PRACTICAL BUTTON */}

              <button
                disabled={
                  busy ||
                  (!progress?.practical_completed &&
                    (tasks.length === 0 ||
                      completedTaskCount !== tasks.length))
                }
                onClick={() => {

                  if (progress?.practical_completed) {

                    setTab('assessment')

                  } else {

                    void finishPractice()

                  }

                }}
                className="learning-primary w-full"
              >

                {progress?.practical_completed
                  ? 'Continue to Assessment'
                  : 'Complete Practical & Start Assessment'}

              </button>

            </div>

          )}

          {/* ==========================================
              TAB 3: DAILY ASSESSMENT
              ========================================== */}

          {tab === 'assessment' && (

            progress?.assessment_completed ? (

              <div className="rounded-xl border
                border-green-900 bg-green-950/30 p-6">

                <h2 className="text-xl font-bold
                  text-green-400">

                  Day Completed Successfully

                </h2>

                <p className="mt-3 text-neutral-300">

                  You have already passed this assessment.

                </p>

                <button
                  onClick={onComplete}
                  className="learning-primary mt-5"
                >

                  Return to Roadmap

                </button>

              </div>

            ) : (

              <DailyAssessment
            key={`${userId}-${dayId}`}
            userId={userId}
            dayId={dayId}
            dayNumber={lesson.day_number}
            onComplete={onComplete}
            />
            )

          )}

        </>

      )}

    </section>

  )
}