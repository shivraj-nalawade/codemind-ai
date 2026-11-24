import { useEffect, useRef, useState } from 'react'

import {
  generateDailyAssessment,
  getDailyAssessment,
  startDailyAttempt,
  getDailyAttempt,
  saveDailyAnswers,
  submitDailyAttempt,
  evaluateDailyAttempt,
  getDailyResult,
  LearningApiError,
} from './learningApi'

import {
  loadAssessmentDraft,
  saveAssessmentDraft,
  clearAssessmentDraft,
} from './learningStorage'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ==========================================
// TYPES
// ==========================================

type Question = {
  question_id: number
  question_type: 'mcq' | 'coding' | 'theory'
  question_text: string
  topic: string
  difficulty: string
  options: string[]
  marks: number
}

type Assessment = {
  assessment_id: number
  title: string
  questions: Question[]
}

type Attempt = {
  attempt_id: number
  assessment_id: number
  attempt_number: number
  status: string
  answers?: {
    question_id: number
    submitted_answer: string
  }[]
}

type Result = {
  passed: boolean
  score: {
    percentage: number
    obtained_marks: number
    total_marks: number
  }
  ai_feedback?: string
  strengths?: string[]
  weaknesses?: string[]
  recommendations?: string[]
  message?: string
}

type Props = {
  userId: number
  dayId: number
  dayNumber: number
  onComplete: () => void
}

// ==========================================
// DAILY ASSESSMENT COMPONENT
// ==========================================

export default function DailyAssessment({
  userId,
  dayId,
  dayNumber,
  onComplete,
}: Props) {

  const [assessment, setAssessment] =
    useState<Assessment | null>(null)

  const [attempt, setAttempt] =
    useState<Attempt | null>(null)

  const [answers, setAnswers] =
    useState<Record<number, string>>({})

  const [result, setResult] =
    useState<Result | null>(null)

  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [draftSaved, setDraftSaved] = useState(false)
  const [serverSaved, setServerSaved] = useState(false)

  const [progressionPending, setProgressionPending] =
    useState(false)

  const answersRef =
    useRef<Record<number, string>>({})

  const actionLock = useRef(false)

  const questions = assessment?.questions ?? []

  const answeredCount = questions.filter(
    question =>
      Boolean(answers[question.question_id]?.trim()),
  ).length

  const progress = questions.length
    ? Math.round(
        answeredCount / questions.length * 100,
      )
    : 0

  // ==========================================
  // LOCAL DRAFT PERSISTENCE
  // ==========================================

  function persistDraft(
    assessmentData: Assessment,
    attemptData: Attempt,
    answerData: Record<number, string>,
  ) {

    const saved = saveAssessmentDraft(
      userId,
      'daily',
      dayId,
      attemptData.attempt_id,
      assessmentData.assessment_id,
      answerData,
      0,
    )

    setDraftSaved(saved)
  }

  // ==========================================
  // RESTORE ASSESSMENT ATTEMPT
  // ==========================================

  async function restoreAttempt(
    assessmentData: Assessment,
    attemptData: Attempt,
  ) {

    if (
      attemptData.assessment_id !==
      assessmentData.assessment_id
    ) {
      throw new Error(
        'The saved attempt belongs to another assessment.',
      )
    }

    const draft = loadAssessmentDraft(
      userId,
      'daily',
      dayId,
    )

    const matchingDraft =
      draft?.attemptId === attemptData.attempt_id &&
      draft?.assessmentId ===
        assessmentData.assessment_id

    const restoredAnswers: Record<number, string> = {}

    // Restore answers saved in the database.

    for (const answer of attemptData.answers ?? []) {

      restoredAnswers[answer.question_id] =
        answer.submitted_answer
    }

    // Restore local answers only for editable attempts.

    if (
      matchingDraft &&
      draft &&
      attemptData.status === 'in_progress'
    ) {

      for (const question of assessmentData.questions) {

        const value =
          draft.answers[question.question_id]

        if (typeof value === 'string') {

          restoredAnswers[question.question_id] =
            value
        }
      }
    }

    setAssessment(assessmentData)
    setAttempt(attemptData)
    setResult(null)
    setProgressionPending(false)
    setServerSaved(false)

    answersRef.current = restoredAnswers

    setAnswers(restoredAnswers)

    persistDraft(
      assessmentData,
      attemptData,
      restoredAnswers,
    )

    // Restore previously evaluated results.

    if (attemptData.status === 'evaluated') {

      const existingResult =
        await getDailyResult(
          attemptData.attempt_id,
        ) as Result

      setResult(existingResult)

      // Recover progression if the assessment passed
      // but the progression transaction was interrupted.

      if (existingResult.passed) {

        setProgressionPending(true)
      }
    }
  }

  // ==========================================
  // AUTOMATIC REFRESH RECOVERY
  // ==========================================

  useEffect(() => {

    let cancelled = false

    async function restore() {

      setLoading(true)
      setError('')

      try {

        const draft = loadAssessmentDraft(
          userId,
          'daily',
          dayId,
        )

        // No saved attempt: show introduction.

        if (!draft) return

        const assessmentData =
          await getDailyAssessment(
            dayId,
          ) as Assessment

        if (cancelled) return

        // Remove outdated assessment references.

        if (
          assessmentData.assessment_id !==
          draft.assessmentId
        ) {

          clearAssessmentDraft(
            userId,
            'daily',
            dayId,
          )

          return
        }

        // Read-only request.
        // Never create another attempt on refresh.

        const attemptData =
          await getDailyAttempt(
            draft.attemptId,
          ) as Attempt

        if (cancelled) return

        await restoreAttempt(
          assessmentData,
          attemptData,
        )

      } catch (err) {

        if (cancelled) return

        // A deleted attempt can no longer be restored.

        if (
          err instanceof LearningApiError &&
          err.status === 404
        ) {

          clearAssessmentDraft(
            userId,
            'daily',
            dayId,
          )

          return
        }

        // The assessment may not be available yet.
        // Allow the learner to generate it manually.

        if (
          err instanceof LearningApiError &&
          err.status === 409
        ) {
          return
        }

        setError(
          err instanceof Error
            ? err.message
            : 'Unable to restore daily assessment.',
        )

      } finally {

        if (!cancelled) {

          setLoading(false)
        }
      }
    }

    void restore()

    return () => {

      cancelled = true
    }

  }, [userId, dayId])

  // ==========================================
  // START OR RETRY ASSESSMENT
  // ==========================================

  async function handleStart(
    retryAssessment = false,
  ) {

    if (actionLock.current) return

    actionLock.current = true

    setBusy(true)
    setError('')

    setStatus(
      retryAssessment
        ? 'Preparing another assessment attempt...'
        : 'Preparing your daily assessment...',
    )

    try {

      // IMPORTANT:
      // Generate first to prevent HTTP 409 when
      // the daily assessment does not exist.

      await generateDailyAssessment(dayId)

      const assessmentData =
        await getDailyAssessment(
          dayId,
        ) as Assessment

      if (
        !Array.isArray(assessmentData.questions) ||
        assessmentData.questions.length !== 5
      ) {

        throw new Error(
          'The daily assessment must contain five questions.',
        )
      }

      const draft = loadAssessmentDraft(
        userId,
        'daily',
        dayId,
      )

      // Restore an existing attempt unless the
      // learner explicitly requests a new attempt.

      if (
        !retryAssessment &&
        draft &&
        draft.assessmentId ===
          assessmentData.assessment_id
      ) {

        try {

          const existingAttempt =
            await getDailyAttempt(
              draft.attemptId,
            ) as Attempt

          await restoreAttempt(
            assessmentData,
            existingAttempt,
          )

          return

        } catch (err) {

          if (
            !(err instanceof LearningApiError) ||
            err.status !== 404
          ) {

            throw err
          }

          clearAssessmentDraft(
            userId,
            'daily',
            dayId,
          )
        }
      }

      // Start or resume a server-side attempt.

      const attemptData =
        await startDailyAttempt(
          dayId,
        ) as Attempt

      await restoreAttempt(
        assessmentData,
        attemptData,
      )

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Unable to prepare daily assessment.',
      )

    } finally {

      actionLock.current = false

      setBusy(false)
      setStatus('')
    }
  }

  // ==========================================
  // UPDATE ANSWER AND AUTO-SAVE
  // ==========================================

  function updateAnswer(
    questionId: number,
    value: string,
  ) {

    if (
      !assessment ||
      !attempt ||
      attempt.status !== 'in_progress' ||
      actionLock.current
    ) {

      return
    }

    const updatedAnswers = {
      ...answersRef.current,
      [questionId]: value,
    }

    answersRef.current = updatedAnswers

    setAnswers(updatedAnswers)
    setServerSaved(false)

    // Save immediately in localStorage.
    // Includes MCQs and partially written answers.

    persistDraft(
      assessment,
      attempt,
      updatedAnswers,
    )
  }

  // ==========================================
  // SAVE DRAFT TO DATABASE
  // ==========================================

  async function saveDraftToServer() {

    if (
      !assessment ||
      !attempt ||
      attempt.status !== 'in_progress' ||
      actionLock.current
    ) {

      return
    }

    const answerPayload = questions
      .filter(
        question =>
          answersRef.current[
            question.question_id
          ] !== undefined,
      )
      .map(question => ({
        question_id: question.question_id,
        submitted_answer:
          answersRef.current[
            question.question_id
          ],
      }))

    if (!answerPayload.length) return

    actionLock.current = true

    setBusy(true)
    setError('')
    setStatus('Saving answers to your account...')

    try {

      await saveDailyAnswers(
        attempt.attempt_id,
        answerPayload,
      )

      setServerSaved(true)

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Unable to save answers to the server.',
      )

    } finally {

      actionLock.current = false

      setBusy(false)
      setStatus('')
    }
  }

  // ==========================================
  // CHECK SERVER ATTEMPT STATUS
  // ==========================================

  async function refreshAttempt() {

    if (
      !assessment ||
      !attempt ||
      actionLock.current
    ) {

      return
    }

    actionLock.current = true

    setBusy(true)
    setError('')
    setStatus('Checking assessment status...')

    try {

      const latestAttempt =
        await getDailyAttempt(
          attempt.attempt_id,
        ) as Attempt

      await restoreAttempt(
        assessment,
        latestAttempt,
      )

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Unable to retrieve assessment status.',
      )

    } finally {

      actionLock.current = false

      setBusy(false)
      setStatus('')
    }
  }

  // ==========================================
  // SUBMIT AND EVALUATE
  // ==========================================

  async function handleSubmit() {

    if (
      !assessment ||
      !attempt ||
      actionLock.current
    ) {

      return
    }

    setError('')

    const allAnswered =
      questions.length === 5 &&
      questions.every(
        question =>
          Boolean(
            answersRef.current[
              question.question_id
            ]?.trim(),
          ),
      )

    if (
      attempt.status === 'in_progress' &&
      !allAnswered
    ) {

      setError(
        'Please answer all five questions before submitting.',
      )

      return
    }

    actionLock.current = true

    setBusy(true)

    try {

      // Check authoritative server status.

      let currentAttempt =
        await getDailyAttempt(
          attempt.attempt_id,
        ) as Attempt

      if (currentAttempt.status === 'evaluating') {

        setAttempt(currentAttempt)

        setError(
          'Evaluation is already running. Check the status shortly.',
        )

        return
      }

      // Save and submit only editable attempts.

      if (currentAttempt.status === 'in_progress') {

        if (!allAnswered) {

          throw new Error(
            'Please answer all five questions.',
          )
        }

        setStatus(
          'Saving your assessment answers...',
        )

        await saveDailyAnswers(
          currentAttempt.attempt_id,
          questions.map(question => ({
            question_id: question.question_id,
            submitted_answer:
              answersRef.current[
                question.question_id
              ] ?? '',
          })),
        )

        setServerSaved(true)

        setStatus(
          'Submitting daily assessment...',
        )

        currentAttempt =
          await submitDailyAttempt(
            currentAttempt.attempt_id,
          ) as Attempt

        setAttempt(currentAttempt)
      }

      if (currentAttempt.status === 'evaluating') {

        setAttempt(currentAttempt)

        return
      }

      // Recover already evaluated attempts.

      if (currentAttempt.status === 'evaluated') {

        const existingResult =
          await getDailyResult(
            currentAttempt.attempt_id,
          ) as Result

        setResult(existingResult)
        setAttempt(currentAttempt)

        if (!existingResult.passed) {

          setProgressionPending(false)

          return
        }

        // The result is already evaluated.
        // Retry only the backend's idempotent
        // evaluation/progression operation.

        setProgressionPending(true)

        setStatus(
          'Recovering your learning progress...',
        )

        await evaluateDailyAttempt(
          currentAttempt.attempt_id,
        )

        setProgressionPending(false)

        return
      }

      if (
        currentAttempt.status !== 'submitted' &&
        currentAttempt.status !== 'failed'
      ) {

        throw new Error(
          'Assessment is not ready for evaluation.',
        )
      }

      setAttempt(currentAttempt)

      setStatus(
        'AI is evaluating your answers. Please wait...',
      )

      // Evaluate answers and finalize progression.

      await evaluateDailyAttempt(
        currentAttempt.attempt_id,
      )

      const evaluatedResult =
        await getDailyResult(
          currentAttempt.attempt_id,
        ) as Result

      setResult(evaluatedResult)

      setAttempt({
        ...currentAttempt,
        status: 'evaluated',
      })

      setProgressionPending(false)

      // Retain the local attempt reference
      // so the result can survive a refresh.

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Evaluation failed. Your answers are saved.',
      )

      // Recover server state if the request
      // failed or the connection was interrupted.

      try {

        const latestAttempt =
          await getDailyAttempt(
            attempt.attempt_id,
          ) as Attempt

        await restoreAttempt(
          assessment,
          latestAttempt,
        )

      } catch {

        // Keep the local draft if the
        // server is temporarily unavailable.
      }

    } finally {

      actionLock.current = false

      setBusy(false)
      setStatus('')
    }
  }

  // ==========================================
  // COMPLETE DAY
  // ==========================================

  function handleComplete() {

    if (
      !result?.passed ||
      progressionPending ||
      actionLock.current
    ) {

      return
    }

    clearAssessmentDraft(
      userId,
      'daily',
      dayId,
    )

    onComplete()
  }

  // ==========================================
  // LOADING SCREEN
  // ==========================================

  if (loading) {

    return (

      <div className="flex items-center gap-4 p-8">

        <div className="h-7 w-7 animate-spin
          rounded-full border-2 border-orange-500
          border-t-transparent"
        />

        <p className="text-orange-400">

          Restoring your daily assessment...

        </p>

      </div>
    )
  }

  // ==========================================
  // MAIN INTERFACE
  // ==========================================

  return (

    <section className="space-y-6">

      {/* HEADER */}

      <div>

        <p className="text-sm font-bold uppercase
          tracking-widest text-orange-500">

          Day {dayNumber} · Knowledge Assessment

        </p>

        <h2 className="mt-2 text-3xl font-bold">

          Daily Assessment

        </h2>

        <p className="mt-2 text-neutral-400">

          Test your understanding and demonstrate
          your programming skills.

        </p>

      </div>

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
            border border-orange-500/20
            bg-orange-500/10 p-5"
        >

          <div className="h-7 w-7 shrink-0 animate-spin
            rounded-full border-2 border-orange-500
            border-t-transparent"
          />

          <div>

            <p className="font-medium text-orange-400">

              {status || 'Processing your request...'}

            </p>

            <p className="mt-1 text-sm text-neutral-400">

              Please wait while your progress is saved.

            </p>

          </div>

        </div>

      )}

      {/* ======================================
          ASSESSMENT RESULTS
          ====================================== */}

      {result ? (

        <div className="space-y-6">

          <div className={`rounded-2xl border
            bg-[#191919] p-8 ${
              result.passed
                ? 'border-green-800'
                : 'border-orange-800'
            }`}>

            <p className={`text-sm font-semibold ${
              result.passed
                ? 'text-green-400'
                : 'text-orange-400'
            }`}>

              {result.passed
                ? '✓ Assessment Passed'
                : 'Assessment Completed'}

            </p>

            <h2 className="mt-3 text-3xl font-bold">

              {result.passed
                ? 'Great Work!'
                : 'Keep Practicing!'}

            </h2>

            <p className="mt-3 text-neutral-400">

              {result.passed
                ? 'You have achieved the required passing score.'
                : result.message ??
                  'Review the lesson and try again.'}

            </p>

            {/* SCORE CARDS */}

            <div className="mt-7 grid gap-4
              sm:grid-cols-3">

              <div className="rounded-xl
                bg-neutral-900 p-5">

                <p className="text-sm text-neutral-400">

                  Your Score

                </p>

                <p className={`mt-2 text-3xl
                  font-bold ${
                    result.passed
                      ? 'text-green-400'
                      : 'text-orange-400'
                  }`}>

                  {result.score.percentage}%

                </p>

              </div>

              <div className="rounded-xl
                bg-neutral-900 p-5">

                <p className="text-sm text-neutral-400">

                  Marks Obtained

                </p>

                <p className="mt-2 text-3xl font-bold">

                  {result.score.obtained_marks}
                  /{result.score.total_marks}

                </p>

              </div>

              <div className="rounded-xl
                bg-neutral-900 p-5">

                <p className="text-sm text-neutral-400">

                  Passing Score

                </p>

                <p className="mt-2 text-3xl
                  font-bold text-orange-400">

                  80%

                </p>

              </div>

            </div>

            {/* SCORE PROGRESS BAR */}

            <div className="mt-7">

              <div className="relative h-3
                overflow-hidden rounded-full
                bg-neutral-800">

                <div
                  className={`h-full rounded-full ${
                    result.passed
                      ? 'bg-green-500'
                      : 'bg-orange-500'
                  }`}
                  style={{
                    width: `${Math.min(
                      100,
                      Math.max(
                        0,
                        result.score.percentage,
                      ),
                    )}%`,
                  }}
                />

                <div className="absolute inset-y-0
                  left-[80%] w-0.5 bg-white"
                />

              </div>

              <div className="mt-2 flex
                justify-between text-xs
                text-neutral-500">

                <span>0%</span>

                <span>Passing threshold: 80%</span>

                <span>100%</span>

              </div>

            </div>

          </div>

          {/* AI FEEDBACK */}

          {result.ai_feedback && (

            <article className="rounded-2xl border
              border-neutral-800 bg-[#191919] p-6">

              <h3 className="mb-4 text-xl font-bold">

                Personalized AI Feedback

              </h3>

              <div className="learning-markdown">

                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                >

                  {result.ai_feedback}

                </ReactMarkdown>

              </div>

            </article>

          )}

          {/* STRENGTHS AND WEAKNESSES */}

          {(
            (result.strengths ?? []).length > 0 ||
            (result.weaknesses ?? []).length > 0
          ) && (

            <div className="grid gap-5 md:grid-cols-2">

              <article className="rounded-2xl border
                border-green-900 bg-[#191919] p-6">

                <h3 className="mb-4 text-xl
                  font-bold text-green-400">

                  Your Strengths

                </h3>

                {(result.strengths ?? []).map(
                  (item, index) => (

                    <p
                      key={index}
                      className="mb-3 text-neutral-300"
                    >

                      ✓ {item}

                    </p>

                  ),
                )}

              </article>

              <article className="rounded-2xl border
                border-orange-900 bg-[#191919] p-6">

                <h3 className="mb-4 text-xl
                  font-bold text-orange-400">

                  Areas for Improvement

                </h3>

                {(result.weaknesses ?? []).map(
                  (item, index) => (

                    <p
                      key={index}
                      className="mb-3 text-neutral-300"
                    >

                      • {item}

                    </p>

                  ),
                )}

              </article>

            </div>

          )}

          {/* RECOMMENDATIONS */}

          {(result.recommendations ?? []).length > 0 && (

            <article className="rounded-2xl border
              border-neutral-800 bg-[#191919] p-6">

              <h3 className="mb-4 text-xl font-bold">

                Recommended Next Steps

              </h3>

              <div className="space-y-3">

                {(result.recommendations ?? []).map(
                  (item, index) => (

                    <div
                      key={index}
                      className="rounded-xl
                        bg-neutral-900 p-4"
                    >

                      <span className="mr-3
                        font-bold text-orange-400">

                        {index + 1}.

                      </span>

                      {item}

                    </div>

                  ),
                )}

              </div>

            </article>

          )}

          {/* RESULT ACTIONS */}

          {result.passed ? (

            progressionPending ? (

              <div className="rounded-xl border
                border-orange-900 bg-orange-500/5 p-5">

                <p className="mb-4 text-orange-400">

                  Your assessment result is saved.
                  Confirm your learning progression
                  before continuing.

                </p>

                <button
                  disabled={busy}
                  onClick={() => void handleSubmit()}
                  className="learning-primary w-full"
                >

                  Confirm Learning Progress

                </button>

              </div>

            ) : (

              <button
                disabled={busy}
                onClick={handleComplete}
                className="learning-primary w-full"
              >

                Complete Day & Return to Roadmap →

              </button>

            )

          ) : (

            <div className="space-y-4">

              <div className="rounded-xl border
                border-orange-900 bg-orange-500/5 p-5">

                <p className="font-semibold
                  text-orange-400">

                  Another attempt is required.

                </p>

                <p className="mt-2 text-sm
                  text-neutral-400">

                  You need at least 80% to unlock
                  the next learning day. Review
                  the lesson and practical exercises
                  before trying again.

                </p>

              </div>

              <button
                disabled={busy}
                onClick={() => void handleStart(true)}
                className="learning-primary w-full"
              >

                Retry Daily Assessment

              </button>

            </div>

          )}

        </div>

      ) : !assessment || !attempt ? (

        /* ======================================
           ASSESSMENT INTRODUCTION
           ====================================== */

        <div className="rounded-2xl border
          border-neutral-800 bg-[#191919] p-8">

          <h2 className="text-2xl font-bold">

            Ready to Test Your Knowledge?

          </h2>

          <p className="mt-4 leading-relaxed
            text-neutral-400">

            Complete this assessment to demonstrate
            your understanding of today's lesson
            and unlock the next learning day.

          </p>

          <div className="my-7 grid grid-cols-2
            gap-4 md:grid-cols-4">

            {[
              ['5', 'Total Questions'],
              ['3', 'MCQ Questions'],
              ['2', 'Written Questions'],
              ['80%', 'Passing Score'],
            ].map(([value, label]) => (

              <div
                key={label}
                className="rounded-xl
                  bg-neutral-900 p-5"
              >

                <p className="text-3xl font-bold
                  text-orange-400">

                  {value}

                </p>

                <p className="mt-2 text-sm
                  text-neutral-400">

                  {label}

                </p>

              </div>

            ))}

          </div>

          <div className="mb-6 space-y-3
            rounded-xl border border-neutral-800
            bg-neutral-900 p-5">

            <h3 className="font-semibold">

              Assessment Instructions

            </h3>

            <p className="text-sm text-neutral-400">

              • Answer all five questions.

            </p>

            <p className="text-sm text-neutral-400">

              • Three MCQs, one coding question
              and one theory question.

            </p>

            <p className="text-sm text-neutral-400">

              • Total assessment marks: 9.

            </p>

            <p className="text-sm text-neutral-400">

              • Written answers are evaluated by AI.

            </p>

            <p className="text-sm text-neutral-400">

              • Score at least 80% to unlock the next day.

            </p>

            <p className="text-sm text-green-400">

              ✓ Your answers are automatically
              saved in this browser.

            </p>

          </div>

          <button
            disabled={busy}
            onClick={() => void handleStart()}
            className="learning-primary w-full"
          >

            {busy
              ? 'Preparing assessment...'
              : 'Start or Resume Daily Assessment'}

          </button>

        </div>

      ) : attempt.status !== 'in_progress' ? (

        /* ======================================
           SUBMITTED / EVALUATING / FAILED
           ====================================== */

        <div className="rounded-2xl border
          border-neutral-800 bg-[#191919] p-8">

          <h2 className="text-2xl font-bold">

            {attempt.status === 'evaluating'
              ? 'Evaluation in Progress'
              : attempt.status === 'evaluated'
                ? 'Assessment Evaluated'
                : 'Assessment Submitted'}

          </h2>

          <p className="mt-4 leading-relaxed
            text-neutral-400">

            Your submitted answers are preserved.
            You do not need to answer the questions again.

          </p>

          {attempt.status === 'failed' && (

            <p className="mt-4 text-orange-400">

              The previous AI evaluation could not
              finish. Retry to evaluate your saved
              answers.

            </p>

          )}

          <div className="mt-6 flex flex-wrap gap-4">

            <button
              disabled={busy}
              onClick={() => void refreshAttempt()}
              className="rounded-xl border
                border-neutral-700 px-5 py-3
                hover:border-orange-500
                disabled:opacity-50"
            >

              Check Assessment Status

            </button>

            {['submitted', 'failed'].includes(
              attempt.status,
            ) && (

              <button
                disabled={busy}
                onClick={() => void handleSubmit()}
                className="learning-primary"
              >

                {attempt.status === 'failed'
                  ? 'Retry AI Evaluation'
                  : 'Continue AI Evaluation'}

              </button>

            )}

          </div>

        </div>

      ) : (

        /* ======================================
           ACTIVE DAILY ASSESSMENT
           ====================================== */

        <div className="space-y-6">

          {/* PROGRESS HEADER */}

          <div className="rounded-2xl border
            border-neutral-800 bg-[#191919] p-5">

            <div className="flex flex-wrap
              items-center justify-between gap-3">

              <div>

                <p className="font-semibold">

                  Assessment Progress

                </p>

                <p className="mt-1 text-xs
                  text-neutral-500">

                  Attempt {attempt.attempt_number}

                </p>

              </div>

              <p className="font-medium
                text-orange-400">

                {answeredCount}/{questions.length}
                {' '}Answered

              </p>

            </div>

            <div className="mt-4 h-2
              overflow-hidden rounded-full
              bg-neutral-800">

              <div
                className="h-full rounded-full
                  bg-orange-500 transition-all"
                style={{
                  width: `${progress}%`,
                }}
              />

            </div>

            <div className="mt-4 flex flex-wrap
              items-center justify-between gap-3">

              <div className="space-y-1">

                <p className={`text-xs ${
                  draftSaved
                    ? 'text-green-400'
                    : 'text-neutral-500'
                }`}>

                  {draftSaved
                    ? '✓ Draft saved in this browser'
                    : 'Local draft not saved yet'}

                </p>

                {serverSaved && (

                  <p className="text-xs text-green-400">

                    ✓ Progress saved to your account

                  </p>

                )}

              </div>

              <button
                disabled={
                  busy ||
                  Object.keys(answers).length === 0
                }
                onClick={() =>
                  void saveDraftToServer()
                }
                className="rounded-lg border
                  border-neutral-700 px-4 py-2
                  text-xs text-orange-400
                  hover:border-orange-500
                  disabled:opacity-40"
              >

                Save Progress to Account

              </button>

            </div>

          </div>

          {/* ALL ASSESSMENT QUESTIONS */}

          {questions.map((question, index) => (

            <article
              key={question.question_id}
              className="rounded-2xl border
                border-neutral-800 bg-[#191919] p-7"
            >

              {/* QUESTION HEADER */}

              <div className="flex flex-wrap
                items-center justify-between gap-3">

                <p className="font-semibold
                  text-orange-400">

                  Question {index + 1}

                </p>

                <div className="flex flex-wrap gap-2">

                  {answers[question.question_id]?.trim() && (

                    <span className="rounded-lg
                      bg-green-500/10 px-3 py-1
                      text-xs text-green-400">

                      ✓ Answered

                    </span>

                  )}

                  <span className="rounded-lg
                    bg-neutral-800 px-3 py-1
                    text-xs capitalize">

                    {question.question_type}

                  </span>

                  <span className="rounded-lg
                    bg-orange-500/10 px-3 py-1
                    text-xs capitalize text-orange-400">

                    {question.difficulty}

                  </span>

                  <span className="rounded-lg
                    bg-neutral-800 px-3 py-1 text-xs">

                    {question.marks}
                    {' '}
                    {question.marks === 1
                      ? 'Mark'
                      : 'Marks'}

                  </span>

                </div>

              </div>

              <p className="mt-5 text-sm
                text-neutral-400">

                Topic: {question.topic}

              </p>

              {/* MARKDOWN QUESTION */}

              <div className="learning-markdown
                my-6 text-lg">

                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                >

                  {question.question_text}

                </ReactMarkdown>

              </div>

              {/* MCQ OPTIONS */}

              {question.question_type === 'mcq' ? (

                <div className="space-y-3">

                  {(question.options ?? []).map(
                    (option, optionIndex) => (

                      <button
                        key={optionIndex}
                        disabled={busy}
                        onClick={() =>
                          updateAnswer(
                            question.question_id,
                            option,
                          )
                        }
                        className={`flex w-full
                          items-start gap-4 rounded-xl
                          border p-4 text-left
                          transition-colors
                          disabled:opacity-60 ${
                            answers[
                              question.question_id
                            ] === option
                              ? 'border-orange-500 bg-orange-500/10'
                              : 'border-neutral-700 bg-neutral-900 hover:border-orange-500/50'
                          }`}
                      >

                        <span className="font-bold
                          text-orange-400">

                          {String.fromCharCode(
                            65 + optionIndex,
                          )}.

                        </span>

                        <span className="whitespace-pre-wrap
                          text-neutral-200">

                          {option}

                        </span>

                      </button>

                    ),
                  )}

                </div>

              ) : (

                /* CODING / THEORY ANSWER */

                <div>

                  <textarea
                    rows={
                      question.question_type === 'coding'
                        ? 14
                        : 8
                    }
                    disabled={busy}
                    spellCheck={
                      question.question_type !== 'coding'
                    }
                    maxLength={20000}
                    value={
                      answers[question.question_id] ?? ''
                    }
                    onChange={event =>
                      updateAnswer(
                        question.question_id,
                        event.target.value,
                      )
                    }
                    placeholder={
                      question.question_type === 'coding'
                        ? 'Write your code here...'
                        : 'Explain your answer here...'
                    }
                    className={`learning-input ${
                      question.question_type === 'coding'
                        ? 'font-mono'
                        : ''
                    }`}
                  />

                  <p className="mt-2 text-xs
                    text-neutral-500">

                    {draftSaved
                      ? 'Your draft is saved in this browser.'
                      : 'Type your answer to save a local draft.'}

                  </p>

                </div>

              )}

            </article>

          ))}

          {/* SUBMIT BUTTON */}

          <div className="rounded-2xl border
            border-neutral-800 bg-[#191919] p-6">

            <div className="mb-5 flex flex-wrap
              items-center justify-between gap-3">

              <div>

                <h3 className="text-lg font-semibold">

                  Ready to Submit?

                </h3>

                <p className="mt-1 text-sm
                  text-neutral-400">

                  Your answers cannot be changed
                  after submission.

                </p>

              </div>

              <span className="text-orange-400">

                {answeredCount}/{questions.length}
                {' '}Completed

              </span>

            </div>

            <button
              disabled={
                busy ||
                questions.length !== 5 ||
                answeredCount !== questions.length
              }
              onClick={() => void handleSubmit()}
              className="learning-primary w-full"
            >

              {busy
                ? 'Processing...'
                : 'Submit Daily Assessment'}

            </button>

            {answeredCount !== questions.length && (

              <p className="mt-3 text-center
                text-sm text-neutral-500">

                Answer all five questions before submitting.

              </p>

            )}

          </div>

        </div>

      )}

    </section>
  )
}