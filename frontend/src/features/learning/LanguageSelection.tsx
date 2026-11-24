
import { useEffect, useState } from 'react'

import {
  getLanguages,
  getEnrollments,
  createEnrollment,
} from './learningApi'

import type {
  Language,
  Enrollment,
} from './learningApi'

type Props = {
  onSelect: (enrollment: Enrollment) => void
}

const languageDetails: Record<string, {
  symbol: string
  color: string
  description: string
}> = {
  cpp: {
    symbol: 'C++',
    color: '#659ad2',
    description: 'Master programming fundamentals, OOP and problem solving.',
  },
  python: {
    symbol: 'Py',
    color: '#facc15',
    description: 'Learn Python for automation, software and AI development.',
  },
  javascript: {
    symbol: 'JS',
    color: '#f7df1e',
    description: 'Build interactive web applications and modern software.',
  },
  java: {
    symbol: 'Java',
    color: '#f97316',
    description: 'Explore object-oriented and application development.',
  },
  sql: {
    symbol: 'SQL',
    color: '#38bdf8',
    description: 'Master databases, queries and data management.',
  },
}

export default function LanguageSelection({ onSelect }: Props) {
  const [languages, setLanguages] = useState<Language[]>([])
  const [enrollments, setEnrollments] = useState<Enrollment[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  async function loadData() {
    setLoading(true)
    setError('')

    try {
      const [available, existing] = await Promise.all([
        getLanguages(),
        getEnrollments(),
      ])

      setLanguages(available)
      setEnrollments(existing)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Loading failed.',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  async function selectLanguage(language: string) {
    if (busy) return

    setBusy(language)
    setError('')

    try {
      const existing = enrollments.find(
        item => item.language === language,
      )

      const enrollment = existing
        ?? await createEnrollment(language)

      onSelect(enrollment)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Enrollment failed.',
      )
    } finally {
      setBusy('')
    }
  }

  return (
    <section className="mx-auto max-w-7xl px-6 py-10">

      <p className="text-sm font-semibold uppercase
        tracking-widest text-orange-500">
        Your learning journey
      </p>

      <h1 className="mt-3 text-3xl font-bold md:text-4xl">
        Choose your programming language
      </h1>

      <p className="mt-3 text-neutral-400">
        Start with a skill assessment and receive a personalized
        30-day roadmap.
      </p>

      {error && (
        <div className="mt-6 rounded-lg bg-red-950/40 p-4
          text-red-300">
          {error}
          <button
            className="ml-3 underline"
            onClick={() => void loadData()}
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <p className="mt-10 text-neutral-400">
          Loading programming languages...
        </p>
      ) : (
        <div className="mt-8 grid gap-5 md:grid-cols-2
          xl:grid-cols-3">

          {languages.map(language => {
            const details = languageDetails[language.id]

            const existing = enrollments.find(
              item => item.language === language.id,
            )

            return (
              <article
                key={language.id}
                className="flex flex-col rounded-2xl border
                  border-neutral-800 bg-[#191919] p-6
                  transition hover:border-orange-500/50"
              >
                <div className="flex items-center justify-between">
                  <div
                    className="flex h-16 w-16 items-center
                      justify-center rounded-xl bg-neutral-800
                      text-2xl font-bold"
                    style={{ color: details?.color }}
                  >
                    {details?.symbol ?? language.name}
                  </div>

                  <span className="rounded-full bg-neutral-800
                    px-3 py-1 text-xs text-neutral-300">
                    30 Days
                  </span>
                </div>

                <h2 className="mt-5 text-2xl font-bold">
                  {language.name}
                </h2>

                <p className="mt-2 text-sm leading-relaxed
                  text-neutral-400">
                  {details?.description}
                </p>

                <div className="my-5 flex flex-wrap gap-2">
                  {language.topics.slice(0, 4).map(topic => (
                    <span
                      key={topic}
                      className="rounded-md bg-neutral-800
                        px-2 py-1 text-xs text-neutral-300"
                    >
                      {topic}
                    </span>
                  ))}
                </div>

                {existing && (
                  <div className="mb-4 rounded-lg
                    bg-orange-500/10 p-3 text-sm text-orange-300">
                    {existing.status === 'pending'
                      ? 'Assessment pending'
                      : existing.status === 'completed'
                        ? 'Course completed'
                        : `Continue from Day ${existing.current_day}`}
                  </div>
                )}

                <button
                  disabled={Boolean(busy)}
                  onClick={() => void selectLanguage(language.id)}
                  className="learning-primary mt-auto w-full"
                >
                  {busy === language.id
                    ? 'Please wait...'
                    : existing
                      ? 'Continue learning'
                      : 'Start learning'}
                </button>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
