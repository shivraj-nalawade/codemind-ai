import { useEffect, useState } from 'react'

import {
  getDashboard,
  type Enrollment,
} from './learningApi'

// ==========================================
// TYPES
// ==========================================

type DashboardProps = {
  enrollment: Enrollment
  onBack: () => void
  onSelectDay: (dayId: number) => void
}

type RoadmapDay = {
  learning_day_id: number
  day_number: number
  title: string
  topic: string
  difficulty: string
  estimated_minutes: number
  status: string
  is_accessible: boolean
  lesson_completed: boolean
  practical_completed: boolean
  assessment_completed: boolean
  best_score: number
  next_action?: string
}

type DailyScore = {
  day_number: number
  title: string
  topic: string | null
  best_score: number
  latest_score: number
  attempt_count: number
  passed: boolean
}

type MasteryTopic = {
  topic: string
  initially_assessed: boolean
  initial_score: number | null
  current_mastery: number
  improvement: number | null
  classification: string
  recommended_difficulty: string
  total_questions: number
  correct_answers: number
  accuracy: number
}

type CalendarDay = {
  date: string
  completed_lessons: number
  learning_days: number[]
  is_active: boolean
  is_today: boolean
}

type LearningActivity = {
  event_id: string
  activity_type: string
  description: string
  day_number: number | null
  timestamp: string
}

type DashboardData = {
  enrollment: {
    enrollment_id: number
    language: string
    language_name: string
    skill_level: string
    skill_level_display: string
    status: string
    current_day: number
    course_completed: boolean
  }

  course_progress: {
    planned_days: number
    total_days: number
    completed_days: number
    pending_days: number
    unlocked_days: number
    in_progress_days: number
    locked_days: number
    completed_lessons: number
    completed_practicals: number
    completed_assessments: number
    generated_lessons: number
    overall_progress_percentage: number
    average_completed_day_score: number | null
  }

  streaks: {
    current_streak: number
    longest_streak: number
    active_learning_days: number
    completed_today: boolean
    last_learning_date: string | null
  }

  initial_assessment: {
    percentage: number
    obtained_marks: number
    total_marks: number
    strengths: string[]
    weaknesses: string[]
    recommendations: string[]
    feedback: string
  } | null

  daily_performance: {
    total_evaluated_attempts: number
    passed_attempts: number
    unsuccessful_attempts: number
    assessed_days: number
    passed_days: number
    average_attempt_score: number | null
    average_best_daily_score: number | null
    highest_score: number | null
    lowest_score: number | null
    latest_score: number | null
    attempt_pass_rate: number | null
    passing_percentage: number
    daily_scores: DailyScore[]
  }

  topic_mastery: {
    total_topics: number
    strong_topics: string[]
    developing_topics: string[]
    weak_topics: string[]
    average_initial_mastery: number | null
    average_current_mastery: number | null
    average_mastery_improvement: number | null
    improved_topics_count: number
    most_improved_topic: MasteryTopic | null
    topics: MasteryTopic[]
  }

  current_learning_day: RoadmapDay | null

  upcoming_lessons: RoadmapDay[]

  roadmap: RoadmapDay[]

  study_time: {
    total_estimated_minutes: number
    completed_estimated_minutes: number
    remaining_estimated_minutes: number
    total_estimated_hours: number
    completed_estimated_hours: number
    remaining_estimated_hours: number
  }

  adaptations: {
    total_adaptations: number
    total_lesson_updates: number
    unique_adapted_lessons: number
    adapted_day_numbers: number[]
    latest_adaptation: {
      job_id: number
      completed_day: number | null
      summary: string
      updated_count: number
      completed_at: string | null
    } | null
  }

  learning_calendar: CalendarDay[]

  recent_activities: LearningActivity[]

  recommendations: string[]

  generated_at: string
}

// ==========================================
// HELPER FUNCTIONS
// ==========================================

function percentage(value: number | null): string {
  if (value === null || value === undefined) {
    return '—'
  }

  return `${Number(value).toFixed(2)}%`
}

function clamp(value: number): number {
  return Math.min(100, Math.max(0, value))
}

function formatDate(value: string | null): string {
  if (!value) return 'Not available'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Not available'
  }

  return date.toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Kolkata',
  })
}

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const remaining = minutes % 60

  if (hours === 0) {
    return `${remaining} min`
  }

  return `${hours}h ${remaining}m`
}

function formatLabel(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase())
}

function masteryColor(classification: string): string {
  if (classification === 'strong') {
    return '#22c55e'
  }

  if (classification === 'developing') {
    return '#f59e0b'
  }

  return '#ef4444'
}

function activityIcon(type: string): string {
  switch (type) {
    case 'lesson':
      return '📖'

    case 'practical':
      return '💻'

    case 'assessment':
      return '📝'

    case 'day_completed':
      return '✓'

    case 'roadmap_adaptation':
      return '✦'

    default:
      return '•'
  }
}

// ==========================================
// REUSABLE UI COMPONENTS
// ==========================================

function StatCard({
  label,
  value,
  description,
  color = '#ff8900',
}: {
  label: string
  value: string | number
  description?: string
  color?: string
}) {
  return (
    <div className="rounded-2xl border border-[#292929] bg-[#191919] p-5">
      <p className="text-sm text-gray-400">
        {label}
      </p>

      <h3
        className="mt-3 text-3xl font-bold"
        style={{ color }}
      >
        {value}
      </h3>

      {description && (
        <p className="mt-2 text-xs text-gray-500">
          {description}
        </p>
      )}
    </div>
  )
}

function ProgressBar({
  value,
  color = '#ff8900',
}: {
  value: number
  color?: string
}) {
  return (
    <div
      className="h-2.5 w-full overflow-hidden rounded-full bg-[#303030]"
      role="progressbar"
      aria-valuenow={clamp(value)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{
          width: `${clamp(value)}%`,
          backgroundColor: color,
        }}
      />
    </div>
  )
}

function SectionTitle({
  title,
  description,
}: {
  title: string
  description?: string
}) {
  return (
    <div className="mb-6">
      <h2 className="text-xl font-bold text-white">
        {title}
      </h2>

      {description && (
        <p className="mt-2 text-sm text-gray-400">
          {description}
        </p>
      )}
    </div>
  )
}

function EmptyState({
  message,
}: {
  message: string
}) {
  return (
    <div className="rounded-xl border border-dashed border-[#333] p-8 text-center text-sm text-gray-400">
      {message}
    </div>
  )
}

function TopicList({
  topics,
  emptyMessage,
  color,
}: {
  topics: string[]
  emptyMessage: string
  color: string
}) {
  if (!topics.length) {
    return (
      <p className="text-sm text-gray-500">
        {emptyMessage}
      </p>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {topics.map((topic, index) => (
        <span
          key={`${topic}-${index}`}
          className="rounded-lg px-3 py-2 text-xs"
          style={{
            color,
            backgroundColor: `${color}15`,
            border: `1px solid ${color}35`,
          }}
        >
          {topic}
        </span>
      ))}
    </div>
  )
}

// ==========================================
// ASSESSMENT PERFORMANCE CHART
// ==========================================

function PerformanceChart({
  scores,
  passingPercentage,
}: {
  scores: DailyScore[]
  passingPercentage: number
}) {
  if (!scores.length) {
    return (
      <EmptyState
        message="Complete your first daily assessment to see your performance chart."
      />
    )
  }

  return (
    <div>
      <div className="overflow-x-auto pb-3">
        <div
          className="flex gap-3"
          style={{
            minWidth: Math.max(
              320,
              scores.length * 55 + 45,
            ),
          }}
        >
          {/* Y-axis */}

          <div className="relative h-[240px] w-9 shrink-0 text-xs text-gray-500">
            {[100, 75, 50, 25, 0].map(value => (
              <span
                key={value}
                className="absolute right-0 -translate-y-1/2"
                style={{
                  top: `${100 - value}%`,
                }}
              >
                {value}%
              </span>
            ))}
          </div>

          {/* Chart area */}

          <div className="relative flex-1">
            <div className="relative h-[240px]">

              {[0, 25, 50, 75, 100].map(value => (
                <div
                  key={value}
                  className="absolute w-full border-t border-[#303030]"
                  style={{
                    top: `${100 - value}%`,
                  }}
                />
              ))}

              {/* Passing threshold */}

              <div
                className="absolute z-10 w-full border-t border-dashed border-orange-500"
                style={{
                  bottom: `${clamp(
                    passingPercentage,
                  )}%`,
                }}
              />

              {/* Score bars */}

              <div className="absolute inset-0 flex items-end justify-around gap-3 px-2">
                {scores.map(score => (
                  <div
                    key={score.day_number}
                    className="group relative flex h-full flex-1 items-end justify-center"
                    title={
                      `Day ${score.day_number}: ` +
                      `${score.best_score}% | ` +
                      `${score.attempt_count} attempt(s)`
                    }
                  >
                    <div
                      className="relative w-full max-w-[48px] rounded-t-lg transition-all duration-300 group-hover:brightness-125"
                      style={{
                        height: `${clamp(
                          score.best_score,
                        )}%`,
                        backgroundColor: score.passed
                          ? '#22c55e'
                          : '#f59e0b',
                      }}
                    >
                      <span className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-semibold text-white">
                        {Number(
                          score.best_score,
                        ).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* X-axis */}

            <div className="mt-4 flex justify-around gap-3 px-2">
              {scores.map(score => (
                <div
                  key={score.day_number}
                  className="flex-1 text-center text-xs text-gray-400"
                >
                  D{score.day_number}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Legend */}

      <div className="mt-5 flex flex-wrap gap-5 text-xs text-gray-400">
        <span className="flex items-center gap-2">
          <span className="h-3 w-3 rounded bg-green-500" />
          Passed
        </span>

        <span className="flex items-center gap-2">
          <span className="h-3 w-3 rounded bg-amber-500" />
          Below passing score
        </span>

        <span className="flex items-center gap-2">
          <span className="w-5 border-t border-dashed border-orange-500" />
          {passingPercentage}% passing threshold
        </span>
      </div>
    </div>
  )
}

// ==========================================
// MAIN DASHBOARD COMPONENT
// ==========================================

export default function LearningDashboard({
  enrollment,
  onBack,
  onSelectDay,
}: DashboardProps) {

  const [dashboard, setDashboard] =
    useState<DashboardData | null>(null)

  const [loading, setLoading] = useState(true)

  const [error, setError] = useState('')

  const [refreshCount, setRefreshCount] =
    useState(0)

  const [masteryFilter, setMasteryFilter] =
    useState('all')

  // ========================================
  // FETCH DASHBOARD
  // ========================================

  useEffect(() => {
    let cancelled = false

    async function fetchDashboard() {
      setLoading(true)
      setError('')
      setDashboard(null)

      try {
        const data = await getDashboard(
          enrollment.id,
        ) as DashboardData

        if (!cancelled) {
          setDashboard(data)
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to load learning dashboard.',
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void fetchDashboard()

    return () => {
      cancelled = true
    }
  }, [enrollment.id, refreshCount])

  // ========================================
  // LOADING STATE
  // ========================================

  if (loading) {
    return (
      <div className="flex min-h-[500px] flex-col items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-[#333] border-t-orange-500" />

        <h2 className="mt-6 text-xl font-semibold text-white">
          Loading your analytics
        </h2>

        <p className="mt-2 text-sm text-gray-400">
          Retrieving your learning progress...
        </p>
      </div>
    )
  }

  // ========================================
  // ERROR STATE
  // ========================================

  if (error || !dashboard) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <button
          onClick={onBack}
          className="mb-6 text-orange-500 hover:text-orange-400"
        >
          ← Back to roadmap
        </button>

        <div className="rounded-2xl border border-red-900 bg-red-950/30 p-6">
          <h2 className="text-xl font-semibold text-red-400">
            Unable to load dashboard
          </h2>

          <p className="mt-3 text-red-300">
            {error || 'Dashboard data is unavailable.'}
          </p>

          <button
            onClick={() =>
              setRefreshCount(value => value + 1)
            }
            className="mt-5 rounded-lg bg-orange-500 px-5 py-3 font-semibold text-black"
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  // ========================================
  // DASHBOARD DATA
  // ========================================

  const progress = dashboard.course_progress

  const streaks = dashboard.streaks

  const performance = dashboard.daily_performance

  const mastery = dashboard.topic_mastery

  const studyTime = dashboard.study_time

  const initial = dashboard.initial_assessment

  const currentDay = dashboard.current_learning_day

  const adaptations = dashboard.adaptations

  const filteredTopics = mastery.topics.filter(
    topic =>
      masteryFilter === 'all' ||
      topic.classification === masteryFilter,
  )

  // ========================================
  // DASHBOARD UI
  // ========================================

  return (
    <div className="min-h-screen bg-[#111111] text-white">

      <div className="mx-auto max-w-7xl space-y-8 px-5 py-8 lg:px-8">

        {/* =================================
            HEADER
        ================================= */}

        <div className="flex flex-wrap items-center justify-between gap-4">

          <button
            onClick={onBack}
            className="text-sm font-medium text-orange-500 hover:text-orange-400"
          >
            ← Back to roadmap
          </button>

          <button
            onClick={() =>
              setRefreshCount(value => value + 1)
            }
            className="rounded-lg border border-[#333] bg-[#191919] px-4 py-2 text-sm text-gray-300 transition hover:border-orange-500 hover:text-orange-500"
          >
            ↻ Refresh Analytics
          </button>

        </div>

        <div>
          <p className="text-sm font-bold uppercase tracking-widest text-orange-500">
            Personalized Learning Analytics
          </p>

          <h1 className="mt-3 text-3xl font-bold md:text-4xl">
            Your {dashboard.enrollment.language_name}
            {' '}Learning Dashboard
          </h1>

          <p className="mt-3 text-gray-400">
            Track your performance, understand your
            strengths and monitor your personalized
            learning journey.
          </p>

          <div className="mt-4 flex flex-wrap gap-3">

            <span className="rounded-full border border-orange-500/30 bg-orange-500/10 px-4 py-2 text-xs font-medium text-orange-400">
              {dashboard.enrollment.skill_level_display}
            </span>

            <span className="rounded-full border border-green-500/30 bg-green-500/10 px-4 py-2 text-xs font-medium text-green-400">
              {formatLabel(
                dashboard.enrollment.status,
              )}
            </span>

          </div>
        </div>

        {/* =================================
            OVERVIEW STATISTICS
        ================================= */}

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">

          <StatCard
            label="Course Progress"
            value={percentage(
              progress.overall_progress_percentage,
            )}
            description={
              `${progress.completed_days} of ` +
              `${progress.planned_days} days completed`
            }
          />

          <StatCard
            label="Average Daily Score"
            value={percentage(
              performance.average_best_daily_score,
            )}
            description="Best score from each assessed day"
            color="#22c55e"
          />

          <StatCard
            label="Current Streak"
            value={`${streaks.current_streak} days`}
            description={
              `Longest streak: ${streaks.longest_streak} days`
            }
          />

          <StatCard
            label="Average Topic Mastery"
            value={percentage(
              mastery.average_current_mastery,
            )}
            description={
              `${mastery.total_topics} topics tracked`
            }
            color="#a78bfa"
          />

        </div>

        {/* =================================
            COURSE PROGRESS
        ================================= */}

        <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

          <SectionTitle
            title="Overall Learning Progress"
            description="Your progress across the personalized 30-day roadmap."
          />

          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm text-gray-400">
              Course completion
            </span>

            <span className="font-semibold text-orange-500">
              {percentage(
                progress.overall_progress_percentage,
              )}
            </span>
          </div>

          <ProgressBar
            value={
              progress.overall_progress_percentage
            }
          />

          <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">

            {[
              {
                label: 'Completed',
                value: progress.completed_days,
                color: '#22c55e',
              },
              {
                label: 'In Progress',
                value: progress.in_progress_days,
                color: '#f59e0b',
              },
              {
                label: 'Unlocked',
                value: progress.unlocked_days,
                color: '#60a5fa',
              },
              {
                label: 'Locked',
                value: progress.locked_days,
                color: '#9ca3af',
              },
            ].map(item => (
              <div
                key={item.label}
                className="rounded-xl bg-[#141414] p-4"
              >
                <p className="text-xs text-gray-400">
                  {item.label}
                </p>

                <p
                  className="mt-2 text-2xl font-bold"
                  style={{ color: item.color }}
                >
                  {item.value}
                </p>
              </div>
            ))}

          </div>

          <div className="mt-7 space-y-5">

            {[
              {
                label: 'Lessons Completed',
                count: progress.completed_lessons,
              },
              {
                label: 'Practical Sessions Completed',
                count: progress.completed_practicals,
              },
              {
                label: 'Assessments Passed',
                count: progress.completed_assessments,
              },
            ].map(item => (
              <div key={item.label}>

                <div className="mb-2 flex justify-between text-sm">

                  <span className="text-gray-300">
                    {item.label}
                  </span>

                  <span className="text-orange-400">
                    {item.count} / {progress.planned_days}
                  </span>

                </div>

                <ProgressBar
                  value={
                    progress.planned_days
                      ? item.count /
                        progress.planned_days * 100
                      : 0
                  }
                />

              </div>
            ))}

          </div>
        </section>

        {/* =================================
            CURRENT LEARNING DAY
        ================================= */}

        {currentDay && (
          <section className="rounded-2xl border border-orange-500/30 bg-orange-500/5 p-6">

            <p className="text-sm font-bold uppercase tracking-wider text-orange-500">
              Continue Learning
            </p>

            <h2 className="mt-3 text-2xl font-bold">
              Day {currentDay.day_number}:{' '}
              {currentDay.title}
            </h2>

            <p className="mt-2 text-sm text-gray-400">
              {currentDay.topic}
              {' · '}
              {currentDay.estimated_minutes} minutes
              {' · '}
              {formatLabel(currentDay.difficulty)}
            </p>

            <div className="mt-5 flex flex-wrap gap-3 text-xs">

              <span className="rounded-lg bg-[#222] px-3 py-2">
                Lesson: {
                  currentDay.lesson_completed
                    ? 'Completed'
                    : 'Pending'
                }
              </span>

              <span className="rounded-lg bg-[#222] px-3 py-2">
                Practical: {
                  currentDay.practical_completed
                    ? 'Completed'
                    : 'Pending'
                }
              </span>

              <span className="rounded-lg bg-[#222] px-3 py-2">
                Assessment: {
                  currentDay.assessment_completed
                    ? 'Completed'
                    : 'Pending'
                }
              </span>

            </div>

            <button
              disabled={!currentDay.is_accessible}
              onClick={() =>
                onSelectDay(
                  currentDay.learning_day_id,
                )
              }
              className="mt-6 rounded-xl bg-orange-500 px-6 py-3 font-semibold text-black transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {currentDay.next_action
                ? formatLabel(currentDay.next_action)
                : 'Continue Learning'}
              {' →'}
            </button>

          </section>
        )}

        {dashboard.enrollment.course_completed && (
          <section className="rounded-2xl border border-green-500/30 bg-green-500/10 p-6">

            <h2 className="text-2xl font-bold text-green-400">
              Congratulations! Course Completed
            </h2>

            <p className="mt-3 text-gray-300">
              You have successfully completed your
              personalized learning roadmap.
            </p>

          </section>
        )}

        {/* =================================
            DAILY ASSESSMENT PERFORMANCE
        ================================= */}

        <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

          <SectionTitle
            title="Daily Assessment Performance"
            description="Track your best assessment score for each learning day."
          />

          <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">

            <StatCard
              label="Highest Score"
              value={percentage(
                performance.highest_score,
              )}
              color="#22c55e"
            />

            <StatCard
              label="Latest Score"
              value={percentage(
                performance.latest_score,
              )}
            />

            <StatCard
              label="Total Attempts"
              value={
                performance.total_evaluated_attempts
              }
              color="#60a5fa"
            />

            <StatCard
              label="Attempt Pass Rate"
              value={percentage(
                performance.attempt_pass_rate,
              )}
              color="#a78bfa"
            />

          </div>

          <PerformanceChart
            scores={performance.daily_scores}
            passingPercentage={
              performance.passing_percentage
            }
          />

          {performance.daily_scores.length > 0 && (
            <div className="mt-8 overflow-x-auto">

              <table className="w-full text-left text-sm">

                <thead>
                  <tr className="border-b border-[#333] text-gray-400">

                    <th className="p-3">Day</th>
                    <th className="p-3">Topic</th>
                    <th className="p-3">Best Score</th>
                    <th className="p-3">Latest Score</th>
                    <th className="p-3">Attempts</th>
                    <th className="p-3">Status</th>

                  </tr>
                </thead>

                <tbody>

                  {performance.daily_scores.map(
                    score => (
                      <tr
                        key={score.day_number}
                        className="border-b border-[#292929] hover:bg-[#202020]"
                      >
                        <td className="p-3 text-orange-400">
                          Day {score.day_number}
                        </td>

                        <td className="p-3 text-gray-300">
                          {score.topic || score.title}
                        </td>

                        <td className="p-3 font-semibold">
                          {percentage(score.best_score)}
                        </td>

                        <td className="p-3">
                          {percentage(
                            score.latest_score,
                          )}
                        </td>

                        <td className="p-3">
                          {score.attempt_count}
                        </td>

                        <td className="p-3">

                          <span
                            className={
                              score.passed
                                ? 'text-green-400'
                                : 'text-amber-400'
                            }
                          >
                            {score.passed
                              ? 'Passed'
                              : 'Retry Required'}
                          </span>

                        </td>
                      </tr>
                    ),
                  )}

                </tbody>
              </table>

            </div>
          )}

        </section>

        {/* =================================
            INITIAL DIAGNOSTIC ASSESSMENT
        ================================= */}

        <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

          <SectionTitle
            title="Initial Diagnostic Assessment"
            description="Your starting performance before personalized learning."
          />

          {!initial ? (
            <EmptyState
              message="Initial assessment results are not available yet."
            />
          ) : (
            <>

              <div className="grid gap-4 sm:grid-cols-3">

                <StatCard
                  label="Initial Score"
                  value={percentage(
                    initial.percentage,
                  )}
                />

                <StatCard
                  label="Marks Obtained"
                  value={
                    `${initial.obtained_marks} / ` +
                    `${initial.total_marks}`
                  }
                />

                <StatCard
                  label="Assigned Skill Level"
                  value={
                    dashboard.enrollment
                      .skill_level_display
                  }
                  color="#a78bfa"
                />

              </div>

              <div className="mt-6 grid gap-5 md:grid-cols-2">

                <div className="rounded-xl bg-[#141414] p-5">

                  <h3 className="mb-4 font-semibold text-green-400">
                    Initial Strengths
                  </h3>

                  <TopicList
                    topics={initial.strengths}
                    emptyMessage="No initial strengths recorded."
                    color="#22c55e"
                  />

                </div>

                <div className="rounded-xl bg-[#141414] p-5">

                  <h3 className="mb-4 font-semibold text-red-400">
                    Initial Weaknesses
                  </h3>

                  <TopicList
                    topics={initial.weaknesses}
                    emptyMessage="No initial weaknesses recorded."
                    color="#ef4444"
                  />

                </div>

              </div>

              {initial.feedback && (
                <div className="mt-5 rounded-xl bg-[#141414] p-5">

                  <h3 className="mb-3 font-semibold text-orange-400">
                    AI Assessment Feedback
                  </h3>

                  <p className="whitespace-pre-wrap text-sm leading-7 text-gray-300">
                    {initial.feedback}
                  </p>

                </div>
              )}

            </>
          )}

        </section>

        {/* =================================
            TOPIC MASTERY
        ================================= */}

        <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

          <SectionTitle
            title="Topic Mastery Analytics"
            description="Understand your current knowledge level and improvement across programming topics."
          />

          <div className="grid grid-cols-3 gap-3">

            <StatCard
              label="Strong Topics"
              value={mastery.strong_topics.length}
              color="#22c55e"
            />

            <StatCard
              label="Developing"
              value={
                mastery.developing_topics.length
              }
              color="#f59e0b"
            />

            <StatCard
              label="Needs Practice"
              value={mastery.weak_topics.length}
              color="#ef4444"
            />

          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-2">

            <StatCard
              label="Average Mastery Improvement"
              value={
                mastery.average_mastery_improvement === null
                  ? '—'
                  : `${mastery.average_mastery_improvement > 0 ? '+' : ''}${Number(
                      mastery.average_mastery_improvement,
                    ).toFixed(2)} pp`
              }
              description="Topics assessed in the initial diagnostic"
              color="#22c55e"
            />

            <StatCard
              label="Improved Topics"
              value={mastery.improved_topics_count}
              description={
                mastery.most_improved_topic
                  ? `Most improved: ${mastery.most_improved_topic.topic}`
                  : 'Keep practicing to improve mastery'
              }
            />

          </div>

          {/* Topic filters */}

          <div className="my-6 flex flex-wrap gap-2">

            {[
              { value: 'all', label: 'All Topics' },
              { value: 'strong', label: 'Strong' },
              {
                value: 'developing',
                label: 'Developing',
              },
              {
                value: 'weak',
                label: 'Needs Practice',
              },
            ].map(filter => (
              <button
                key={filter.value}
                onClick={() =>
                  setMasteryFilter(filter.value)
                }
                className={
                  `rounded-lg px-4 py-2 text-sm transition ${
                    masteryFilter === filter.value
                      ? 'bg-orange-500 font-semibold text-black'
                      : 'bg-[#262626] text-gray-400 hover:text-white'
                  }`
                }
              >
                {filter.label}
              </button>
            ))}

          </div>

          {filteredTopics.length === 0 ? (
            <EmptyState
              message="No topics are available in this category."
            />
          ) : (
            <div className="space-y-4">

              {filteredTopics.map(topic => (
                <div
                  key={topic.topic}
                  className="rounded-xl border border-[#292929] bg-[#141414] p-5"
                >

                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">

                    <h3 className="font-semibold">
                      {topic.topic}
                    </h3>

                    <span
                      className="rounded-full px-3 py-1 text-xs"
                      style={{
                        color: masteryColor(
                          topic.classification,
                        ),
                        backgroundColor:
                          `${masteryColor(
                            topic.classification,
                          )}15`,
                      }}
                    >
                      {formatLabel(
                        topic.classification,
                      )}
                    </span>

                  </div>

                  {topic.initial_score !== null && (
                    <div className="mb-4">

                      <div className="mb-2 flex justify-between text-xs text-gray-400">

                        <span>Initial Mastery</span>

                        <span>
                          {percentage(
                            topic.initial_score,
                          )}
                        </span>

                      </div>

                      <ProgressBar
                        value={topic.initial_score}
                        color="#64748b"
                      />

                    </div>
                  )}

                  <div>

                    <div className="mb-2 flex justify-between text-sm">

                      <span className="text-gray-300">
                        Current Mastery
                      </span>

                      <span
                        style={{
                          color: masteryColor(
                            topic.classification,
                          ),
                        }}
                      >
                        {percentage(
                          topic.current_mastery,
                        )}
                      </span>

                    </div>

                    <ProgressBar
                      value={topic.current_mastery}
                      color={masteryColor(
                        topic.classification,
                      )}
                    />

                  </div>

                  <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs text-gray-400">

                    <span>
                      Accuracy: {
                        percentage(topic.accuracy)
                      }
                    </span>

                    <span>
                      Correct: {topic.correct_answers}
                      /{topic.total_questions}
                    </span>

                    <span>
                      Difficulty: {
                        formatLabel(
                          topic.recommended_difficulty,
                        )
                      }
                    </span>

                    {topic.improvement !== null && (
                      <span
                        className={
                          topic.improvement >= 0
                            ? 'text-green-400'
                            : 'text-red-400'
                        }
                      >
                        Change: {
                          topic.improvement > 0
                            ? '+'
                            : ''
                        }
                        {topic.improvement} pp
                      </span>
                    )}

                  </div>

                </div>
              ))}

            </div>
          )}

        </section>

        {/* =================================
            LEARNING STREAK AND CALENDAR
        ================================= */}

        <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

          <SectionTitle
            title="Learning Streak & Activity"
            description="Your learning consistency over the last 30 calendar days."
          />

          <div className="grid gap-4 sm:grid-cols-3">

            <StatCard
              label="Current Streak"
              value={`${streaks.current_streak} days`}
            />

            <StatCard
              label="Longest Streak"
              value={`${streaks.longest_streak} days`}
              color="#f59e0b"
            />

            <StatCard
              label="Active Learning Dates"
              value={streaks.active_learning_days}
              color="#22c55e"
            />

          </div>

          <div className="mt-6 rounded-xl bg-[#141414] p-5">

            <h3 className="mb-5 font-semibold">
              Last 30 Days
            </h3>

            <div className="grid grid-cols-6 gap-2 sm:grid-cols-10 lg:grid-cols-15">

              {dashboard.learning_calendar.map(
                day => (
                  <div
                    key={day.date}
                    title={
                      `${day.date}: ` +
                      `${day.completed_lessons} learning day(s) completed`
                    }
                    aria-label={
                      `${day.date}, ` +
                      `${day.completed_lessons} completed`
                    }
                    className={
                      `flex aspect-square flex-col items-center justify-center rounded-lg text-xs ${
                        day.is_today
                          ? 'ring-2 ring-orange-500'
                          : ''
                      } ${
                        day.is_active
                          ? 'bg-green-600/30 text-green-400'
                          : 'bg-[#292929] text-gray-500'
                      }`
                    }
                  >
                    <span>
                      {day.date.slice(-2)}
                    </span>

                    {day.is_active && (
                      <span className="mt-1 font-bold">
                        ✓
                      </span>
                    )}

                  </div>
                ),
              )}

            </div>

            <div className="mt-5 flex flex-wrap gap-5 text-xs text-gray-400">

              <span className="flex items-center gap-2">
                <span className="h-3 w-3 rounded bg-[#292929]" />
                No completed day
              </span>

              <span className="flex items-center gap-2">
                <span className="h-3 w-3 rounded bg-green-600/50" />
                Learning completed
              </span>

              <span className="flex items-center gap-2">
                <span className="h-3 w-3 rounded border border-orange-500" />
                Today
              </span>

            </div>

            <p className="mt-5 text-sm text-gray-400">
              {streaks.completed_today
                ? 'You have completed a learning day today. Keep up the consistency!'
                : 'Complete a learning day today to build your streak.'}
            </p>

          </div>

        </section>

        {/* =================================
            ESTIMATED STUDY TIME
        ================================= */}

        <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

          <SectionTitle
            title="Estimated Study Time"
            description="Based on the planned duration of your personalized lessons, not actual time spent."
          />

          <div className="grid gap-4 sm:grid-cols-3">

            <StatCard
              label="Total Estimated Time"
              value={formatDuration(
                studyTime.total_estimated_minutes,
              )}
            />

            <StatCard
              label="Completed Estimated Time"
              value={formatDuration(
                studyTime.completed_estimated_minutes,
              )}
              color="#22c55e"
            />

            <StatCard
              label="Remaining Estimated Time"
              value={formatDuration(
                studyTime.remaining_estimated_minutes,
              )}
              color="#60a5fa"
            />

          </div>

          <div className="mt-6">

            <ProgressBar
              value={
                studyTime.total_estimated_minutes
                  ? studyTime.completed_estimated_minutes /
                    studyTime.total_estimated_minutes * 100
                  : 0
              }
              color="#22c55e"
            />

          </div>

        </section>

        {/* =================================
            AI ROADMAP ADAPTATION
        ================================= */}

        <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

          <SectionTitle
            title="AI Roadmap Personalization"
            description="See how your learning roadmap has adapted to your assessment performance."
          />

          <div className="grid gap-4 sm:grid-cols-3">

            <StatCard
              label="Completed Adaptations"
              value={adaptations.total_adaptations}
            />

            <StatCard
              label="Total Lesson Updates"
              value={adaptations.total_lesson_updates}
              color="#a78bfa"
            />

            <StatCard
              label="Unique Adapted Lessons"
              value={
                adaptations.unique_adapted_lessons
              }
              color="#22c55e"
            />

          </div>

          {adaptations.latest_adaptation ? (
            <div className="mt-6 rounded-xl border border-orange-500/20 bg-orange-500/5 p-5">

              <h3 className="font-semibold text-orange-400">
                Latest AI Adaptation
              </h3>

              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-300">
                {
                  adaptations.latest_adaptation.summary ||
                  'Your personalized roadmap has been processed.'
                }
              </p>

              <p className="mt-4 text-xs text-gray-500">
                Updated {
                  adaptations.latest_adaptation
                    .updated_count
                } lessons
                {' · '}
                {formatDate(
                  adaptations.latest_adaptation
                    .completed_at,
                )}
              </p>

            </div>
          ) : (
            <div className="mt-5">
              <EmptyState
                message="Roadmap adaptations will appear here after completed adaptation jobs."
              />
            </div>
          )}

        </section>

        {/* =================================
            UPCOMING LESSONS
        ================================= */}

        <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

          <SectionTitle
            title="Upcoming Lessons"
            description="Your next personalized learning topics."
          />

          {!dashboard.upcoming_lessons.length ? (
            <EmptyState
              message="No upcoming lessons are available."
            />
          ) : (
            <div className="space-y-3">

              {dashboard.upcoming_lessons.map(day => (
                <div
                  key={day.learning_day_id}
                  className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[#292929] bg-[#141414] p-5"
                >

                  <div className="flex items-center gap-4">

                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-orange-500/10 font-bold text-orange-500">
                      {String(day.day_number).padStart(
                        2,
                        '0',
                      )}
                    </div>

                    <div>

                      <h3 className="font-semibold">
                        {day.title}
                      </h3>

                      <p className="mt-2 text-xs text-gray-400">
                        {day.topic}
                        {' · '}
                        {day.estimated_minutes} min
                        {' · '}
                        {formatLabel(day.difficulty)}
                      </p>

                    </div>

                  </div>

                  {day.is_accessible ? (
                    <button
                      onClick={() =>
                        onSelectDay(
                          day.learning_day_id,
                        )
                      }
                      className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-semibold text-black hover:bg-orange-400"
                    >
                      Open Lesson →
                    </button>
                  ) : (
                    <span className="rounded-lg bg-[#262626] px-4 py-2 text-xs text-gray-500">
                      🔒 Locked
                    </span>
                  )}

                </div>
              ))}

            </div>
          )}

        </section>

        {/* =================================
            RECOMMENDATIONS AND ACTIVITY
        ================================= */}

        <div className="grid gap-6 lg:grid-cols-2">

          {/* Recommendations */}

          <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

            <SectionTitle
              title="Personalized Recommendations"
              description="Suggested next steps based on your learning performance."
            />

            {dashboard.recommendations.length === 0 ? (
              <EmptyState
                message="No recommendations available yet."
              />
            ) : (
              <div className="space-y-4">

                {dashboard.recommendations.map(
                  (recommendation, index) => (
                    <div
                      key={index}
                      className="flex items-start gap-3 rounded-xl border border-orange-500/10 bg-orange-500/5 p-4"
                    >

                      <span className="mt-1 text-orange-500">
                        ✦
                      </span>

                      <p className="text-sm leading-6 text-gray-300">
                        {recommendation}
                      </p>

                    </div>
                  ),
                )}

              </div>
            )}

          </section>

          {/* Recent activities */}

          <section className="rounded-2xl border border-[#292929] bg-[#191919] p-6">

            <SectionTitle
              title="Recent Learning Activity"
              description="Your latest lessons, assessments and roadmap updates."
            />

            {!dashboard.recent_activities.length ? (
              <EmptyState
                message="Your recent learning activities will appear here."
              />
            ) : (
              <div className="space-y-4">

                {dashboard.recent_activities.map(
                  activity => (
                    <div
                      key={activity.event_id}
                      className="flex items-start gap-3 border-b border-[#292929] pb-4 last:border-0"
                    >

                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-500/10 text-orange-400">
                        {activityIcon(
                          activity.activity_type,
                        )}
                      </div>

                      <div>

                        <p className="text-sm font-medium text-gray-200">
                          {activity.description}
                        </p>

                        <p className="mt-2 text-xs text-gray-500">
                          {formatDate(
                            activity.timestamp,
                          )}
                        </p>

                      </div>

                    </div>
                  ),
                )}

              </div>
            )}

          </section>

        </div>

        {/* =================================
            FOOTER
        ================================= */}

        <div className="border-t border-[#292929] py-6 text-center">

          <p className="text-xs text-gray-500">
            CodeMind AI · Personalized Learning Analytics
          </p>

          <p className="mt-2 text-xs text-gray-600">
            Last updated: {
              formatDate(dashboard.generated_at)
            }
          </p>

        </div>

      </div>

    </div>
  )
}