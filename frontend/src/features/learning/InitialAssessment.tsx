import { useEffect, useRef, useState } from 'react'

import {
  generateInitialAssessment,
  getInitialAssessment,
  startAssessment,
  saveAnswers,
  submitAssessment,
  evaluateAssessment,
  getAssessmentResult,
  generateRoadmap,
  getEnrollment,
  LearningApiError,
} from './learningApi'

import type { Enrollment } from './learningApi'

import {
  loadAssessmentDraft,
  saveAssessmentDraft,
  clearAssessmentDraft,
} from './learningStorage'

type Question = {
  question_id: number
  order: number
  question_type: 'mcq' | 'coding' | 'theory'
  topic: string
  difficulty: string
  question_text: string
  options: string[]
  marks: number
}

type Assessment = {
  assessment_id: number
  title: string
  total_questions: number
  total_marks: number
  questions: Question[]
}

type Attempt = {
  attempt_id: number
  assessment_id: number
  status: string
  answers: {
    question_id: number
    submitted_answer: string
  }[]
}

type Result = {
  percentage: number
  obtained_marks: number
  total_marks: number
  skill_level: string
  strengths: string[]
  weaknesses: string[]
  recommendations: string[]
  ai_feedback: string
}

type Props = {
  userId: number
  enrollment: Enrollment
  onComplete: (enrollment: Enrollment) => void
}

export default function InitialAssessment({
  userId,
  enrollment,
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

  const [currentIndex, setCurrentIndex] = useState(0)

  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [draftSaved, setDraftSaved] = useState(false)

  const answersRef = useRef<Record<number, string>>({})
  const actionLock = useRef(false)

  const questions = assessment?.questions ?? []
  const question = questions[currentIndex]

  const answeredCount = questions.filter(
    q => Boolean(answers[q.question_id]?.trim()),
  ).length

  const progress = questions.length
    ? Math.round(answeredCount / questions.length * 100)
    : 0

  // ==========================================
  // LOCAL DRAFT PERSISTENCE
  // ==========================================

  function persistDraft(
    assessmentData: Assessment,
    attemptData: Attempt,
    answerData: Record<number, string>,
    index: number,
  ) {

    const saved = saveAssessmentDraft(
      userId,
      'initial',
      enrollment.id,
      attemptData.attempt_id,
      assessmentData.assessment_id,
      answerData,
      index,
    )

    setDraftSaved(saved)
  }

  // ==========================================
  // RESTORE ASSESSMENT STATE
  // ==========================================

  async function restoreAttempt(
    assessmentData: Assessment,
    attemptData: Attempt,
  ) {

    const draft = loadAssessmentDraft(
      userId,
      'initial',
      enrollment.id,
    )

    const matchingDraft =
      draft?.attemptId === attemptData.attempt_id &&
      draft?.assessmentId === assessmentData.assessment_id

    const restoredAnswers: Record<number, string> = {}

    // Restore database answers first.
    for (const answer of attemptData.answers ?? []) {

      restoredAnswers[answer.question_id] =
        answer.submitted_answer
    }

    // Restore unsaved browser answers only if the
    // assessment is still editable.
    if (
      matchingDraft &&
      draft &&
      attemptData.status === 'in_progress'
    ) {

      for (const q of assessmentData.questions) {

        const value = draft.answers[q.question_id]

        if (typeof value === 'string') {

          restoredAnswers[q.question_id] = value
        }
      }
    }

    const restoredIndex =
      matchingDraft && draft
        ? Math.min(
            Math.max(draft.currentIndex, 0),
            Math.max(
              assessmentData.questions.length - 1,
              0,
            ),
          )
        : 0

    setAssessment(assessmentData)
    setAttempt(attemptData)
    setResult(null)

    answersRef.current = restoredAnswers

    setAnswers(restoredAnswers)
    setCurrentIndex(restoredIndex)

    persistDraft(
      assessmentData,
      attemptData,
      restoredAnswers,
      restoredIndex,
    )

    // Retrieve an already evaluated result.
    if (attemptData.status === 'evaluated') {

      const existingResult =
        await getAssessmentResult(
          attemptData.attempt_id,
        ) as Result

      setResult(existingResult)
    }
  }

  // ==========================================
  // AUTOMATIC RECOVERY AFTER REFRESH
  // ==========================================

  useEffect(() => {

    let cancelled = false

    async function restore() {

      setLoading(true)
      setError('')

      try {

        const draft = loadAssessmentDraft(
          userId,
          'initial',
          enrollment.id,
        )

        // No saved attempt: display the introduction.
        if (
          !draft &&
          enrollment.skill_level === 'unassessed'
        ) {
          return
        }

        const assessmentData =
          await getInitialAssessment(
            enrollment.id,
          ) as Assessment

        if (cancelled) return

        // The existing backend returns the latest
        // initial attempt instead of creating duplicates.
        const attemptData =
          await startAssessment(
            assessmentData.assessment_id,
          ) as Attempt

        if (cancelled) return

        await restoreAttempt(
          assessmentData,
          attemptData,
        )

      } catch (err) {

        if (cancelled) return

        if (
          err instanceof LearningApiError &&
          err.status === 404
        ) {
          return
        }

        setError(
          err instanceof Error
            ? err.message
            : 'Unable to restore assessment.',
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

  }, [userId, enrollment.id])

  // ==========================================
  // START OR RESUME ASSESSMENT
  // ==========================================

  async function handleStart() {

    if (actionLock.current) return

    actionLock.current = true

    setBusy(true)
    setError('')
    setStatus('Preparing your personalized assessment...')

    try {

      let assessmentData: Assessment

      // Retrieve existing questions before generating.
      try {

        assessmentData =
          await getInitialAssessment(
            enrollment.id,
          ) as Assessment

      } catch (err) {

        if (
          !(err instanceof LearningApiError) ||
          err.status !== 404
        ) {
          throw err
        }

        await generateInitialAssessment(enrollment.id)

        assessmentData =
          await getInitialAssessment(
            enrollment.id,
          ) as Assessment
      }

      const attemptData =
        await startAssessment(
          assessmentData.assessment_id,
        ) as Attempt

      await restoreAttempt(
        assessmentData,
        attemptData,
      )

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Unable to prepare assessment.',
      )

    } finally {

      actionLock.current = false
      setBusy(false)
      setStatus('')
    }
  }

  // ==========================================
  // AUTO-SAVE ANSWERS LOCALLY
  // ==========================================

  function updateAnswer(value: string) {

    if (
      !question ||
      !assessment ||
      !attempt ||
      attempt.status !== 'in_progress' ||
      actionLock.current
    ) {
      return
    }

    const updatedAnswers = {
      ...answersRef.current,
      [question.question_id]: value,
    }

    answersRef.current = updatedAnswers

    setAnswers(updatedAnswers)

    // Save immediately, including partially typed code.
    persistDraft(
      assessment,
      attempt,
      updatedAnswers,
      currentIndex,
    )
  }

  // ==========================================
  // SAVE CURRENT ANSWER TO DATABASE
  // ==========================================

  async function saveCurrentAnswer() {

    if (
      !attempt ||
      !question ||
      attempt.status !== 'in_progress'
    ) {
      return
    }

    const value =
      answersRef.current[question.question_id]

    if (value === undefined) return

    await saveAnswers(
      attempt.attempt_id,
      [
        {
          question_id: question.question_id,
          submitted_answer: value,
        },
      ],
    )
  }

  // ==========================================
  // QUESTION NAVIGATION
  // ==========================================

  async function navigate(index: number) {

    if (
      actionLock.current ||
      !assessment ||
      !attempt ||
      index < 0 ||
      index >= questions.length
    ) {
      return
    }

    actionLock.current = true

    setBusy(true)
    setError('')

    try {

      await saveCurrentAnswer()

      setCurrentIndex(index)

      persistDraft(
        assessment,
        attempt,
        answersRef.current,
        index,
      )

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Unable to save answer.',
      )

    } finally {

      actionLock.current = false
      setBusy(false)
    }
  }

  // ==========================================
  // CHECK CURRENT SERVER STATUS
  // ==========================================

  async function refreshAttempt() {

    if (!assessment || actionLock.current) return

    actionLock.current = true

    setBusy(true)
    setError('')
    setStatus('Checking assessment status...')

    try {

      const latestAttempt =
        await startAssessment(
          assessment.assessment_id,
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
      !attempt ||
      !assessment ||
      actionLock.current
    ) {
      return
    }

    setError('')

    const allAnswered = questions.every(
      q => Boolean(
        answersRef.current[q.question_id]?.trim(),
      ),
    )

    if (
      attempt.status === 'in_progress' &&
      !allAnswered
    ) {

      setError(
        'Please answer all questions before submitting.',
      )

      return
    }

    actionLock.current = true
    setBusy(true)

    try {

      // Always check the authoritative server state.
      let currentAttempt =
        await startAssessment(
          assessment.assessment_id,
        ) as Attempt

      if (
        currentAttempt.attempt_id !== attempt.attempt_id
      ) {

        await restoreAttempt(
          assessment,
          currentAttempt,
        )

        return
      }

      if (currentAttempt.status === 'evaluated') {

        await restoreAttempt(
          assessment,
          currentAttempt,
        )

        return
      }

      if (currentAttempt.status === 'evaluating') {

        setAttempt(currentAttempt)

        setError(
          'Evaluation is already running. Check the status shortly.',
        )

        return
      }

      if (currentAttempt.status === 'in_progress') {

        setStatus('Saving all your answers...')

        await saveAnswers(
          currentAttempt.attempt_id,
          questions.map(q => ({
            question_id: q.question_id,
            submitted_answer:
              answersRef.current[q.question_id] ?? '',
          })),
        )

        setStatus('Submitting assessment...')

        currentAttempt =
          await submitAssessment(
            currentAttempt.attempt_id,
          ) as Attempt

        setAttempt(currentAttempt)
      }

      if (currentAttempt.status === 'evaluated') {

        await restoreAttempt(
          assessment,
          currentAttempt,
        )

        return
      }

      if (currentAttempt.status === 'evaluating') {

        setAttempt(currentAttempt)
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

      const evaluated =
        await evaluateAssessment(
          currentAttempt.attempt_id,
        ) as Result

      setResult(evaluated)

      setAttempt({
        ...currentAttempt,
        status: 'evaluated',
      })

      // Retain the attempt reference until roadmap
      // generation succeeds, allowing result recovery.

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Evaluation failed. Please retry.',
      )

      // Recover the actual server status after failure.
      try {

        const latestAttempt =
          await startAssessment(
            assessment.assessment_id,
          ) as Attempt

        await restoreAttempt(
          assessment,
          latestAttempt,
        )

      } catch {
        // Preserve local answers if recovery is unavailable.
      }

    } finally {

      actionLock.current = false
      setBusy(false)
      setStatus('')
    }
  }

  // ==========================================
  // GENERATE PERSONALIZED ROADMAP
  // ==========================================

  async function handleGenerateRoadmap() {

    if (actionLock.current || !result) return

    actionLock.current = true

    setBusy(true)
    setError('')

    setStatus(
      'Creating your personalized 30-day roadmap...',
    )

    try {

      await generateRoadmap(enrollment.id)

      const updatedEnrollment =
        await getEnrollment(enrollment.id)

      clearAssessmentDraft(
        userId,
        'initial',
        enrollment.id,
      )

      onComplete(updatedEnrollment)

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Unable to generate roadmap. Please retry.',
      )

    } finally {

      actionLock.current = false
      setBusy(false)
      setStatus('')
    }
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
          Restoring assessment progress...
        </p>

      </div>
    )
  }

  // ==========================================
  // MAIN INTERFACE
  // ==========================================

  return (

    <section className="mx-auto max-w-5xl
      space-y-6 py-6">

      {/* HEADER */}

      <div>

        <p className="text-sm font-bold uppercase
          tracking-widest text-orange-500">

          Personalized Learning

        </p>

        <h1 className="mt-2 text-3xl font-bold">

          {enrollment.language_name} Initial Assessment

        </h1>

        <p className="mt-2 text-neutral-400">

          Discover your current programming skill level
          and receive a personalized learning roadmap.

        </p>

      </div>

      {/* ERROR MESSAGE */}

      {error && (

        <div role="alert"
          className="rounded-xl border border-red-900
            bg-red-950/40 p-4 text-red-300">

          {error}

        </div>

      )}

      {/* PROCESSING STATUS */}

      {busy && (

        <div role="status"
          className="flex items-center gap-4 rounded-xl
            border border-orange-500/20
            bg-orange-500/10 p-5">

          <div className="h-7 w-7 shrink-0 animate-spin
            rounded-full border-2 border-orange-500
            border-t-transparent"
          />

          <div>

            <p className="font-medium text-orange-400">

              {status || 'Saving your progress...'}

            </p>

            <p className="mt-1 text-sm text-neutral-400">

              Please wait while your request is processed.

            </p>

          </div>

        </div>

      )}

      {/* ======================================
          ASSESSMENT RESULT
          ====================================== */}

      {result ? (

        <div className="space-y-6">

          <div className="rounded-2xl border
            border-orange-500/30 bg-[#191919] p-8">

            <p className="text-sm font-semibold
              text-orange-400">

              Assessment Completed

            </p>

            <h2 className="mt-3 text-3xl font-bold">

              Your Assessment Results

            </h2>

            <div className="mt-7 grid gap-4 sm:grid-cols-3">

              <div className="rounded-xl bg-neutral-900 p-5">

                <p className="text-sm text-neutral-400">
                  Overall Score
                </p>

                <p className="mt-2 text-3xl font-bold
                  text-orange-400">

                  {result.percentage}%

                </p>

              </div>

              <div className="rounded-xl bg-neutral-900 p-5">

                <p className="text-sm text-neutral-400">
                  Marks Obtained
                </p>

                <p className="mt-2 text-3xl font-bold">

                  {result.obtained_marks}/{result.total_marks}

                </p>

              </div>

              <div className="rounded-xl bg-neutral-900 p-5">

                <p className="text-sm text-neutral-400">
                  Skill Level
                </p>

                <p className="mt-2 text-2xl font-bold
                  capitalize text-green-400">

                  {result.skill_level}

                </p>

              </div>

            </div>

          </div>

          {/* STRENGTHS AND WEAKNESSES */}

          <div className="grid gap-5 md:grid-cols-2">

            <div className="rounded-2xl border
              border-green-900 bg-[#191919] p-6">

              <h3 className="mb-4 text-xl font-bold
                text-green-400">

                Your Strengths

              </h3>

              {(result.strengths ?? []).length > 0 ? (

                <ul className="space-y-3">

                  {result.strengths.map((item, index) => (

                    <li key={index}
                      className="text-neutral-300">

                      ✓ {item}

                    </li>

                  ))}

                </ul>

              ) : (

                <p className="text-neutral-400">

                  Your strengths will develop as you learn.

                </p>

              )}

            </div>

            <div className="rounded-2xl border
              border-orange-900 bg-[#191919] p-6">

              <h3 className="mb-4 text-xl font-bold
                text-orange-400">

                Areas for Improvement

              </h3>

              {(result.weaknesses ?? []).length > 0 ? (

                <ul className="space-y-3">

                  {result.weaknesses.map((item, index) => (

                    <li key={index}
                      className="text-neutral-300">

                      • {item}

                    </li>

                  ))}

                </ul>

              ) : (

                <p className="text-neutral-400">

                  No major weaknesses identified.

                </p>

              )}

            </div>

          </div>

          {/* AI FEEDBACK */}

          <div className="rounded-2xl border
            border-neutral-800 bg-[#191919] p-6">

            <h3 className="mb-4 text-xl font-bold">

              Personalized AI Feedback

            </h3>

            <p className="whitespace-pre-wrap
              leading-relaxed text-neutral-300">

              {result.ai_feedback}

            </p>

          </div>

          {/* RECOMMENDATIONS */}

          <div className="rounded-2xl border
            border-neutral-800 bg-[#191919] p-6">

            <h3 className="mb-4 text-xl font-bold">

              Recommended Learning Priorities

            </h3>

            <div className="space-y-3">

              {(result.recommendations ?? []).map(
                (item, index) => (

                  <div key={index}
                    className="flex items-start gap-3
                      rounded-xl bg-neutral-900 p-4">

                    <span className="font-bold
                      text-orange-400">

                      {index + 1}.

                    </span>

                    <p className="text-neutral-300">

                      {item}

                    </p>

                  </div>

                ),
              )}

            </div>

          </div>

          <button
            disabled={busy}
            onClick={() => void handleGenerateRoadmap()}
            className="learning-primary w-full">

            {busy
              ? 'Please wait...'
              : 'Generate My Personalized 30-Day Roadmap'}

          </button>

        </div>

      ) : !assessment || !attempt ? (

        /* ======================================
           ASSESSMENT INTRODUCTION
           ====================================== */

        <div className="rounded-2xl border
          border-neutral-800 bg-[#191919] p-8">

          <h2 className="text-2xl font-bold">

            Let's Understand Your Skill Level

          </h2>

          <p className="mt-4 leading-relaxed
            text-neutral-400">

            This diagnostic assessment helps CodeMind AI
            understand your programming knowledge and
            create a roadmap based on your strengths
            and areas for improvement.

          </p>

          <div className="my-7 grid grid-cols-2
            gap-4 md:grid-cols-4">

            {[
              ['15', 'Total Questions'],
              ['12', 'MCQ Questions'],
              ['3', 'Written Questions'],
              ['21', 'Total Marks'],
            ].map(([value, label]) => (

              <div key={label}
                className="rounded-xl bg-neutral-900 p-5">

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

          <div className="mb-6 space-y-3 rounded-xl
            border border-neutral-800 bg-neutral-900 p-5">

            <h3 className="font-semibold">

              Assessment Instructions

            </h3>

            <p className="text-sm text-neutral-400">

              • Answer every question independently.

            </p>

            <p className="text-sm text-neutral-400">

              • Questions include basic and intermediate topics.

            </p>

            <p className="text-sm text-neutral-400">

              • Written answers are evaluated by AI.

            </p>

            <p className="text-sm text-neutral-400">

              • There is no passing requirement for this
              diagnostic assessment.

            </p>

            <p className="text-sm text-green-400">

              ✓ Your answers are automatically saved
              in this browser.

            </p>

          </div>

          <button
            disabled={busy}
            onClick={() => void handleStart()}
            className="learning-primary w-full">

            {busy
              ? 'Preparing assessment...'
              : 'Start or Resume Assessment'}

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

              The previous evaluation could not finish.
              Retry to continue evaluating your saved answers.

            </p>

          )}

          <div className="mt-6 flex flex-wrap gap-4">

            <button
              disabled={busy}
              onClick={() => void refreshAttempt()}
              className="rounded-xl border
                border-neutral-700 px-5 py-3
                hover:border-orange-500
                disabled:opacity-50">

              Check Assessment Status

            </button>

            {['submitted', 'failed'].includes(
              attempt.status,
            ) && (

              <button
                disabled={busy}
                onClick={() => void handleSubmit()}
                className="learning-primary">

                {attempt.status === 'failed'
                  ? 'Retry AI Evaluation'
                  : 'Continue AI Evaluation'}

              </button>

            )}

          </div>

        </div>

      ) : (

        /* ======================================
           ACTIVE ASSESSMENT
           ====================================== */

        <div className="space-y-6">

          {/* PROGRESS */}

          <div className="rounded-2xl border
            border-neutral-800 bg-[#191919] p-5">

            <div className="flex flex-wrap
              items-center justify-between gap-3">

              <p className="font-semibold">

                Assessment Progress

              </p>

              <p className="text-orange-400">

                {answeredCount}/{questions.length} Answered

              </p>

            </div>

            <div className="mt-4 h-2 overflow-hidden
              rounded-full bg-neutral-800">

              <div
                className="h-full rounded-full
                  bg-orange-500 transition-all"
                style={{ width: `${progress}%` }}
              />

            </div>

            <p className="mt-3 text-xs text-neutral-400">

              {draftSaved
                ? '✓ Draft saved in this browser'
                : 'Local draft not saved yet'}

            </p>

          </div>

          {/* QUESTION NAVIGATION */}

          <div className="flex flex-wrap gap-2">

            {questions.map((q, index) => (

              <button
                key={q.question_id}
                disabled={busy}
                onClick={() => void navigate(index)}
                className={`h-11 w-11 rounded-lg border
                  text-sm font-semibold
                  disabled:opacity-50 ${
                    index === currentIndex
                      ? 'border-orange-500 bg-orange-500 text-black'
                      : answers[q.question_id]?.trim()
                        ? 'border-green-800 bg-green-950 text-green-400'
                        : 'border-neutral-700 bg-neutral-900 text-neutral-400'
                  }`}>

                {index + 1}

              </button>

            ))}

          </div>

          {/* CURRENT QUESTION */}

          {question && (

            <article className="rounded-2xl border
              border-neutral-800 bg-[#191919] p-7">

              <div className="flex flex-wrap
                items-center justify-between gap-3">

                <p className="font-semibold
                  text-orange-400">

                  Question {currentIndex + 1}
                  {' '}of {questions.length}

                </p>

                <div className="flex flex-wrap gap-2">

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

                    {question.marks} Marks

                  </span>

                </div>

              </div>

              <p className="mt-5 text-sm
                text-neutral-400">

                Topic: {question.topic}

              </p>

              <h2 className="my-6 whitespace-pre-wrap
                text-xl font-semibold leading-relaxed">

                {question.question_text}

              </h2>

              {/* MCQ OPTIONS */}

              {question.question_type === 'mcq' ? (

                <div className="space-y-3">

                  {question.options.map((option, index) => (

                    <button
                      key={index}
                      disabled={busy}
                      onClick={() => updateAnswer(option)}
                      className={`flex w-full items-start
                        gap-4 rounded-xl border p-4
                        text-left transition-colors
                        disabled:opacity-60 ${
                          answers[question.question_id] === option
                            ? 'border-orange-500 bg-orange-500/10'
                            : 'border-neutral-700 bg-neutral-900 hover:border-orange-500/50'
                        }`}>

                      <span className="font-bold
                        text-orange-400">

                        {String.fromCharCode(65 + index)}.

                      </span>

                      <span className="whitespace-pre-wrap
                        text-neutral-200">

                        {option}

                      </span>

                    </button>

                  ))}

                </div>

              ) : (

                /* WRITTEN ANSWER */

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
                      updateAnswer(event.target.value)
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

                    Your draft is saved as you type.

                  </p>

                </div>

              )}

            </article>

          )}

          {/* PREVIOUS / NEXT / SUBMIT */}

          <div className="flex flex-wrap
            items-center justify-between gap-4">

            <button
              disabled={busy || currentIndex === 0}
              onClick={() =>
                void navigate(currentIndex - 1)
              }
              className="rounded-xl border
                border-neutral-700 px-6 py-3
                disabled:opacity-40">

              ← Previous

            </button>

            {currentIndex < questions.length - 1 ? (

              <button
                disabled={busy}
                onClick={() =>
                  void navigate(currentIndex + 1)
                }
                className="learning-primary">

                Save & Next →

              </button>

            ) : (

              <button
                disabled={
                  busy ||
                  answeredCount !== questions.length
                }
                onClick={() => void handleSubmit()}
                className="learning-primary">

                Submit Assessment

              </button>

            )}

          </div>

          {answeredCount !== questions.length && (

            <p className="text-center text-sm
              text-neutral-500">

              Answer all questions to submit your assessment.

            </p>

          )}

        </div>

      )}

    </section>
  )
}