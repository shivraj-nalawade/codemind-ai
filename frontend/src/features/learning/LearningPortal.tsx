import { useEffect, useState } from 'react'

import {
  useLocation,
  useNavigate,
  matchPath,
  Navigate,
} from 'react-router-dom'

import AuthPage from './AuthPage'
import LanguageSelection from './LanguageSelection'
import InitialAssessment from './InitialAssessment'
import RoadmapPage from './RoadmapPage'
import DailyLesson from './DailyLesson'
import LearningDashboard from './LearningDashboard'

import {
  initializeCsrf,
  getCurrentUser,
  logoutUser,
  getEnrollment,
  getRoadmap,
  adaptRoadmap,
  LearningApiError,
} from './learningApi'

import type {
  LearningUser,
  Enrollment,
} from './learningApi'

import './learning.css'

export default function LearningPortal() {

  const location = useLocation()
  const navigate = useNavigate()

  // ==================================================
  // URL-BASED NAVIGATION
  // ==================================================

  const dayRoute = matchPath(
    '/learning/:enrollmentId/day/:dayId/:tab',
    location.pathname,
  )

  const roadmapRoute = matchPath(
    '/learning/:enrollmentId/roadmap',
    location.pathname,
  )

  const assessmentRoute = matchPath(
    '/learning/:enrollmentId/assessment',
    location.pathname,
  )

  const dashboardRoute = matchPath(
    '/learning/:enrollmentId/dashboard',
    location.pathname,
  )

  const activeRoute =
    dayRoute ||
    roadmapRoute ||
    assessmentRoute ||
    dashboardRoute

  const enrollmentId = activeRoute
    ? Number(activeRoute.params.enrollmentId)
    : null

  const selectedDay = dayRoute
    ? Number(dayRoute.params.dayId)
    : null

  const isLearning =
    location.pathname === '/learning' ||
    location.pathname.startsWith('/learning/')

  const isLanguagePage =
    location.pathname === '/learning/languages'

  const validEnrollmentId =
    enrollmentId !== null &&
    Number.isSafeInteger(enrollmentId) &&
    enrollmentId > 0

  const validDayId =
    selectedDay === null ||
    (
      Number.isSafeInteger(selectedDay) &&
      selectedDay > 0
    )

  // ==================================================
  // STATE MANAGEMENT
  // ==================================================

  const [user, setUser] =
    useState<LearningUser | null>(null)

  const [enrollment, setEnrollment] =
    useState<Enrollment | null>(null)

  const [loading, setLoading] = useState(true)

  const [enrollmentLoading, setEnrollmentLoading] =
    useState(false)

  const [error, setError] = useState('')
  const [routeError, setRouteError] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const [reloadKey, setReloadKey] = useState(0)

  const [validatedRoute, setValidatedRoute] =
    useState('')

  // ==================================================
  // INITIALIZE AUTHENTICATION
  // ==================================================

  async function initialize() {

    setLoading(true)
    setError('')

    try {

      await initializeCsrf()

      setUser(await getCurrentUser())

    } catch (err) {

      if (
        err instanceof LearningApiError &&
        err.status === 401
      ) {

        setUser(null)

      } else {

        setError(
          err instanceof Error
            ? err.message
            : 'Unable to connect to the learning server.',
        )

      }

    } finally {

      setLoading(false)

    }
  }

  useEffect(() => {
    void initialize()
  }, [])

  // ==================================================
  // RESTORE ENROLLMENT FROM URL
  // ==================================================

  useEffect(() => {

    if (!isLearning || loading || !user) {
      return
    }

    if (!validEnrollmentId || enrollmentId === null) {

      setEnrollment(null)
      setEnrollmentLoading(false)
      setRouteError('')
      setValidatedRoute('')

      return
    }

    if (!validDayId) {

      setRouteError('Invalid learning day.')
      setEnrollmentLoading(false)

      return
    }

    let cancelled = false

    async function restoreEnrollment() {

      setEnrollmentLoading(true)
      setRouteError('')

      try {

        const updated = await getEnrollment(
          enrollmentId!,
        )

        if (cancelled) return

        // Verify that the requested lesson belongs
        // to the selected enrollment and is accessible.

        if (
          selectedDay !== null &&
          updated.status !== 'pending'
        ) {

          const roadmap = await getRoadmap(
            updated.id,
          ) as {
            learning_day_id: number
            is_accessible: boolean
          }[]

          if (cancelled) return

          const requestedDay = roadmap.find(
            day =>
              day.learning_day_id === selectedDay,
          )

          if (!requestedDay) {

            throw new Error(
              'This lesson does not belong to your enrollment.',
            )
          }

          if (!requestedDay.is_accessible) {

            throw new Error(
              'Complete the previous day to unlock this lesson.',
            )
          }
        }

        setEnrollment(updated)
        setValidatedRoute(location.pathname)

      } catch (err) {

        if (cancelled) return

        setEnrollment(null)

        if (
          err instanceof LearningApiError &&
          err.status === 401
        ) {

          setUser(null)

        } else {

          setRouteError(
            err instanceof Error
              ? err.message
              : 'Unable to restore your learning page.',
          )
        }

      } finally {

        if (!cancelled) {
          setEnrollmentLoading(false)
        }
      }
    }

    void restoreEnrollment()

    return () => {
      cancelled = true
    }

  }, [
    user,
    loading,
    isLearning,
    enrollmentId,
    selectedDay,
    validEnrollmentId,
    validDayId,
    location.pathname,
    reloadKey,
  ])

  // ==================================================
  // LOGOUT
  // ==================================================

  async function handleLogout() {

    if (busy) return

    setBusy(true)
    setError('')

    try {

      await logoutUser()

      setUser(null)
      setEnrollment(null)
      setMessage('')
      setRouteError('')
      setValidatedRoute('')

      navigate('/learning', {
        replace: true,
      })

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Logout failed.',
      )

    } finally {

      setBusy(false)

    }
  }

  // ==================================================
  // LANGUAGE AND ENROLLMENT SELECTION
  // ==================================================

  function handleEnrollmentSelect(
    value: Enrollment,
  ) {

    setEnrollment(value)
    setError('')
    setRouteError('')
    setMessage('')

    const destination =
      value.status === 'pending'
        ? `/learning/${value.id}/assessment`
        : `/learning/${value.id}/roadmap`

    navigate(destination)

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  function handleAllLanguages() {

    if (busy) return

    setEnrollment(null)
    setError('')
    setRouteError('')
    setMessage('')

    navigate('/learning/languages')

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  // ==================================================
  // DASHBOARD NAVIGATION
  // ==================================================

  function handleOpenDashboard() {

    if (
      busy ||
      !enrollment ||
      enrollment.status === 'pending'
    ) {
      return
    }

    setError('')
    setRouteError('')
    setMessage('')

    navigate(
      `/learning/${enrollment.id}/dashboard`,
    )

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  function handleDashboardBack() {

    if (busy || !enrollment) return

    setError('')
    setRouteError('')
    setMessage('')

    navigate(
      `/learning/${enrollment.id}/roadmap`,
    )

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  // ==================================================
  // DAILY LESSON SELECTION
  // ==================================================

  function handleDaySelect(dayId: number) {

    if (busy || !enrollment) return

    setError('')
    setRouteError('')
    setMessage('')

    navigate(
      `/learning/${enrollment.id}/day/${dayId}/lesson`,
    )

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  // ==================================================
  // RETURN TO ROADMAP
  // ==================================================

  async function returnToRoadmap(
    completed = false,
  ) {

    if (!enrollment || busy) return

    const previousEnrollment = enrollment

    setBusy(true)
    setError('')
    setMessage('')

    try {

      const updated = await getEnrollment(
        previousEnrollment.id,
      )

      setEnrollment(updated)

      if (completed) {

        if (updated.status === 'completed') {

          setMessage(
            'Congratulations! You have successfully ' +
            'completed your personalized 30-day course.',
          )

        } else if (
          updated.current_day >
          previousEnrollment.current_day
        ) {

          setMessage(
            `Day ${updated.current_day} is unlocked. ` +
            'AI is adapting your upcoming lessons...',
          )

          try {

            await adaptRoadmap(updated.id)

            setMessage(
              `Day ${updated.current_day} is unlocked! ` +
              'Your personalized roadmap has been updated.',
            )

          } catch {

            setMessage(
              `Day ${updated.current_day} is unlocked. ` +
              'Your progress is saved, but roadmap ' +
              'adaptation could not finish.',
            )
          }

        } else {

          setMessage(
            'Assessment result saved. ' +
            'Check your roadmap for the latest progress.',
          )
        }
      }

      navigate(
        `/learning/${updated.id}/roadmap`,
        { replace: completed },
      )

      window.scrollTo({
        top: 0,
        behavior: 'smooth',
      })

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Unable to refresh learning progress.',
      )

    } finally {

      setBusy(false)

    }
  }

  // ==================================================
  // KEEP HIDDEN WORKSPACE FROM REDIRECTING
  // ==================================================

  if (!isLearning) {
    return null
  }

  // ==================================================
  // INITIAL LOADING SCREEN
  // ==================================================

  if (loading) {

    return (
      <div className="flex min-h-[70vh] items-center
        justify-center gap-4 text-orange-400">

        <div className="h-7 w-7 animate-spin
          rounded-full border-2 border-orange-500
          border-t-transparent" />

        Loading Personalized Learning...

      </div>
    )
  }

  // ==================================================
  // CONNECTION ERROR
  // ==================================================

  if (!user && error) {

    return (
      <div className="p-10 text-center">

        <p className="text-red-400">
          {error}
        </p>

        <button
          className="learning-primary mt-5"
          onClick={() => void initialize()}
        >
          Retry connection
        </button>

      </div>
    )
  }

  // ==================================================
  // LOGIN / REGISTRATION
  // ==================================================

  if (!user) {

    return (
      <AuthPage
        onLogin={value => {

          setUser(value)
          setError('')
          setRouteError('')

          // Preserve requested learning URLs after login.

          if (!activeRoute) {

            navigate('/learning/languages', {
              replace: true,
            })
          }
        }}
      />
    )
  }

  // ==================================================
  // DEFAULT AND INVALID ROUTES
  // ==================================================

  if (
    location.pathname === '/learning' ||
    (!isLanguagePage && !activeRoute)
  ) {

    return (
      <Navigate
        to="/learning/languages"
        replace
      />
    )
  }

  if (
    activeRoute &&
    (!validEnrollmentId || !validDayId)
  ) {

    return (
      <Navigate
        to="/learning/languages"
        replace
      />
    )
  }

  if (
    dayRoute &&
    !['lesson', 'practical', 'assessment'].includes(
      dayRoute.params.tab ?? '',
    )
  ) {

    return (
      <Navigate
        to={`/learning/${enrollmentId}/day/${selectedDay}/lesson`}
        replace
      />
    )
  }

  // ==================================================
  // MAIN LEARNING PORTAL
  // ==================================================

  return (

    <div className="min-h-screen bg-[#111111] text-white">

      {/* HEADER */}

      <header className="flex flex-wrap items-center
        justify-between gap-4 border-b border-neutral-800
        bg-[#191919] px-6 py-4">

        <div>

          <h2 className="font-bold text-orange-500">
            CodeMind AI Learning
          </h2>

          <p className="text-xs text-neutral-400">
            Personalized programming education
          </p>

        </div>

        <div className="flex items-center gap-4">

          <span className="text-sm text-neutral-300">
            {user.first_name || user.username}
          </span>

          <button
            disabled={busy}
            onClick={() => void handleLogout()}
            className="rounded-lg border border-neutral-700
              px-4 py-2 text-sm transition
              hover:bg-neutral-800 disabled:opacity-50"
          >
            Logout
          </button>

        </div>

      </header>

      {/* ERROR MESSAGE */}

      {error && (

        <div
          role="alert"
          className="mx-auto mt-4 max-w-6xl rounded-xl
            border border-red-900 bg-red-950/40
            p-4 text-red-300"
        >
          {error}
        </div>

      )}

      {/* SUCCESS MESSAGE */}

      {message && (

        <div
          role="status"
          className="mx-auto mt-4 max-w-6xl rounded-xl
            border border-orange-500/30 bg-orange-500/10
            p-4 text-orange-300"
        >
          {message}
        </div>

      )}

      {/* LANGUAGE SELECTION */}

      {isLanguagePage ? (

        <LanguageSelection
          onSelect={handleEnrollmentSelect}
        />

      ) : (

        <main className="mx-auto max-w-7xl px-6 py-6">

          {/* LEARNING NAVIGATION */}

          <div className="mb-6 flex flex-wrap
            items-center justify-between gap-4">

            <button
              disabled={busy}
              onClick={handleAllLanguages}
              className="text-sm text-orange-400
                hover:text-orange-300 disabled:opacity-50"
            >
              ← All languages
            </button>

            {roadmapRoute &&
              enrollment &&
              enrollment.id === enrollmentId &&
              enrollment.status !== 'pending' &&
              validatedRoute === location.pathname &&
              !enrollmentLoading &&
              !routeError && (

                <button
                  disabled={busy}
                  onClick={handleOpenDashboard}
                  className="flex items-center gap-2
                    rounded-xl bg-orange-500 px-5 py-3
                    text-sm font-semibold text-black
                    transition hover:bg-orange-400
                    disabled:cursor-not-allowed
                    disabled:opacity-50"
                >

                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="19"
                    height="19"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M3 3v18h18" />
                    <path d="M8 16v-3" />
                    <path d="M13 16V8" />
                    <path d="M18 16V5" />
                  </svg>

                  View Analytics Dashboard

                </button>

              )}

          </div>

          {/* ROUTE LOADING */}

          {enrollmentLoading ? (

            <div className="flex min-h-[40vh]
              flex-col items-center justify-center gap-4">

              <div className="h-9 w-9 animate-spin
                rounded-full border-4 border-orange-500
                border-t-transparent" />

              <p className="text-orange-400">
                Restoring your learning progress...
              </p>

            </div>

          ) : routeError ? (

            /* ROUTE ERROR */

            <div className="rounded-xl border
              border-red-900 bg-red-950/30 p-6">

              <h2 className="text-xl font-bold text-red-400">
                Unable to open this page
              </h2>

              <p className="mt-3 text-neutral-300">
                {routeError}
              </p>

              <button
                onClick={() => {
                  setReloadKey(previous => previous + 1)
                }}
                className="learning-primary mt-5"
              >
                Retry
              </button>

              <button
                onClick={handleAllLanguages}
                className="ml-4 text-orange-400"
              >
                All languages
              </button>

            </div>

          ) : !enrollment ||
            enrollment.id !== enrollmentId ||
            validatedRoute !== location.pathname ? (

            <div className="p-8 text-center text-orange-400">
              Loading your learning page...
            </div>

          ) : enrollment.status === 'pending' ? (

            /* INITIAL ASSESSMENT */

            !assessmentRoute ? (

              <Navigate
                to={`/learning/${enrollment.id}/assessment`}
                replace
              />

            ) : (

              <InitialAssessment
                key={`${user.id}-${enrollment.id}`}
                userId={user.id}
                enrollment={enrollment}
                onComplete={handleEnrollmentSelect}
              />

            )

          ) : assessmentRoute ? (

            /* COMPLETED INITIAL ASSESSMENT */

            <Navigate
              to={`/learning/${enrollment.id}/roadmap`}
              replace
            />

          ) : dashboardRoute ? (

            /* LEARNING ANALYTICS DASHBOARD */

            <LearningDashboard
              key={`${user.id}-${enrollment.id}`}
              enrollment={enrollment}
              onBack={handleDashboardBack}
              onSelectDay={handleDaySelect}
            />

          ) : selectedDay !== null ? (

            /* DAILY LESSON */

            <DailyLesson
              key={`${user.id}-${selectedDay}`}
              userId={user.id}
              dayId={selectedDay}
              onBack={() => void returnToRoadmap()}
              onComplete={() => void returnToRoadmap(true)}
            />

          ) : busy ? (

            /* ROADMAP ADAPTATION */

            <div className="flex min-h-[40vh]
              flex-col items-center justify-center gap-4">

              <div className="h-10 w-10 animate-spin
                rounded-full border-4 border-orange-500
                border-t-transparent" />

              <p className="font-semibold text-orange-400">
                Updating your learning roadmap...
              </p>

              <p className="max-w-md text-center
                text-sm text-neutral-400">
                Please wait while your learning progress
                and upcoming lessons are updated.
              </p>

            </div>

          ) : (

            /* PERSONALIZED ROADMAP */

            <RoadmapPage
              key={enrollment.id}
              enrollment={enrollment}
              onSelectDay={handleDaySelect}
            />

          )}

        </main>

      )}

    </div>
  )
}