
import { useEffect, useState } from 'react'

import { getRoadmap } from './learningApi'
import type { Enrollment } from './learningApi'

type RoadmapDay = {
  learning_day_id: number
  day_number: number
  title: string
  topic: string
  difficulty: string
  learning_objectives: string[]
  estimated_minutes: number
  status: string
  is_accessible: boolean
}

type Props = {
  enrollment: Enrollment
  onSelectDay: (dayId: number) => void
}

export default function RoadmapPage({
  enrollment,
  onSelectDay,
}: Props) {

  const [days, setDays] = useState<RoadmapDay[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function loadRoadmap() {
    setLoading(true)
    setError('')

    try {
      const data = await getRoadmap(
        enrollment.id,
      ) as RoadmapDay[]

      setDays(data)

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to load roadmap.',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadRoadmap()
  }, [enrollment.id])

  const completed = days.filter(
    day => day.status === 'completed',
  ).length

  const progressPercentage = completed / 30 * 100

  return (
    <section className="mx-auto max-w-6xl py-6">

      {/* ROADMAP HEADER */}

      <p className="text-sm font-semibold uppercase
        tracking-widest text-orange-500">
        Personalized Learning Roadmap
      </p>

      <h1 className="mt-3 text-3xl font-bold">
        Your 30-Day {enrollment.language_name} Journey
      </h1>

      <p className="mt-3 text-neutral-400">
        AI-generated learning plan based on your assessment
        performance and individual skill level.
      </p>

      {/* ERROR MESSAGE */}

      {error && (
        <div
          role="alert"
          className="mt-5 rounded-xl bg-red-950/40
            p-4 text-red-300"
        >
          {error}

          <button
            onClick={() => void loadRoadmap()}
            className="ml-4 underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* LOADING STATE */}

      {loading ? (

        <div className="mt-8 flex items-center gap-3">

          <div className="h-6 w-6 animate-spin
            rounded-full border-2 border-orange-500
            border-t-transparent" />

          <p className="text-orange-400">
            Loading your roadmap...
          </p>

        </div>

      ) : (

        <>

          {/* PROGRESS SUMMARY */}

          <div className="my-7 grid gap-4 sm:grid-cols-3">

            {[
              ['Skill level', enrollment.skill_level],
              ['Current day', `${enrollment.current_day} / 30`],
              ['Completed', `${completed} / 30 days`],
            ].map(([label, value]) => (

              <div
                key={label}
                className="rounded-xl border border-neutral-800
                  bg-[#191919] p-5"
              >

                <p className="text-sm text-neutral-400">
                  {label}
                </p>

                <p className="mt-2 text-2xl font-bold
                  capitalize text-orange-400">
                  {value}
                </p>

              </div>

            ))}

          </div>

          {/* PROGRESS BAR */}

          <div className="mb-8">

            <div className="mb-2 flex items-center
              justify-between text-sm">

              <span className="text-neutral-400">
                Overall course progress
              </span>

              <span className="font-semibold text-orange-400">
                {progressPercentage.toFixed(2)}%
              </span>

            </div>

            <div
              role="progressbar"
              aria-label="Course progress"
              aria-valuenow={progressPercentage}
              aria-valuemin={0}
              aria-valuemax={100}
              className="h-2 overflow-hidden
                rounded-full bg-neutral-800"
            >

              <div
                className="h-full rounded-full
                  bg-orange-500 transition-all duration-500"
                style={{
                  width: `${progressPercentage}%`,
                }}
              />

            </div>

          </div>

          {/* COURSE COMPLETION MESSAGE */}

          {completed === 30 && (

            <div className="mb-8 rounded-2xl border
              border-green-800 bg-green-950/30 p-6">

              <h2 className="text-2xl font-bold text-green-400">
                Congratulations! Course Completed
              </h2>

              <p className="mt-3 text-neutral-300">
                You have successfully completed your
                personalized 30-day learning journey.
                You can review any lesson below.
              </p>

            </div>

          )}

          {/* ROADMAP DAYS */}

          <div className="grid gap-4 md:grid-cols-2">

            {days.map(day => (

              <article
                key={day.learning_day_id}
                className={`flex flex-col rounded-2xl border
                  bg-[#191919] p-6 transition-all ${
                    day.status === 'completed'
                      ? 'border-green-800'
                      : day.is_accessible
                        ? 'border-orange-500/60'
                        : 'border-neutral-800 opacity-60'
                  }`}
              >

                {/* DAY NUMBER AND STATUS */}

                <div className="flex items-center
                  justify-between gap-3">

                  <span className="font-bold text-orange-400">
                    DAY {String(day.day_number).padStart(2, '0')}
                  </span>

                  <span className={`rounded-full px-3 py-1
                    text-xs capitalize ${
                      day.status === 'completed'
                        ? 'bg-green-950 text-green-400'
                        : day.status === 'in_progress'
                          ? 'bg-orange-500/10 text-orange-400'
                          : day.status === 'unlocked'
                            ? 'bg-orange-500/10 text-orange-300'
                            : 'bg-neutral-800 text-neutral-400'
                    }`}
                  >
                    {day.status.replaceAll('_', ' ')}
                  </span>

                </div>

                {/* LESSON INFORMATION */}

                <h2 className="mt-4 text-xl font-bold">
                  {day.title}
                </h2>

                <p className="mt-2 text-sm text-neutral-400">
                  {day.topic} · {day.estimated_minutes} min
                </p>

                <div>
                  <span className="mt-3 inline-block rounded-md
                    bg-neutral-800 px-3 py-1 text-xs capitalize">
                    {day.difficulty}
                  </span>
                </div>

                {/* LEARNING OBJECTIVES */}

                <div className="mb-5 mt-4 space-y-2">

                  {day.learning_objectives.map(
                    (objective, index) => (

                      <p
                        key={index}
                        className="text-sm text-neutral-300"
                      >
                        • {objective}
                      </p>

                    ),
                  )}

                </div>

                {/* DAILY LEARNING BUTTON */}

                <button
                  type="button"
                  disabled={!day.is_accessible}
                  onClick={() => {
                    if (day.is_accessible) {
                      onSelectDay(day.learning_day_id)
                    }
                  }}
                  className={`mt-auto w-full rounded-lg
                    p-3 text-sm font-semibold transition-all ${
                      day.status === 'completed'
                        ? 'bg-green-950 text-green-400 hover:bg-green-900'
                        : day.is_accessible
                          ? 'cursor-pointer bg-orange-500 text-black hover:bg-orange-600'
                          : 'cursor-not-allowed bg-neutral-800 text-neutral-500'
                    }`}
                >

                  {day.status === 'completed'
                    ? '✓ Review Lesson'
                    : day.is_accessible
                      ? day.status === 'in_progress'
                        ? 'Continue Learning →'
                        : 'Start Learning →'
                      : '🔒 Complete the previous day to unlock'}

                </button>

              </article>

            ))}

          </div>

        </>

      )}

    </section>
  )
}
