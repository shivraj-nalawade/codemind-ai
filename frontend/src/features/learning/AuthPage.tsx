
import { useState } from 'react'
import type { FormEvent } from 'react'

import {
  registerUser,
  loginUser,
} from './learningApi'

import type { LearningUser } from './learningApi'

type Props = {
  onLogin: (user: LearningUser) => void
}

export default function AuthPage({ onLogin }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')

  const [form, setForm] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    confirm_password: '',
  })

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  function updateField(
    field: keyof typeof form,
    value: string,
  ) {
    setForm(previous => ({
      ...previous,
      [field]: value,
    }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (busy) return

    setBusy(true)
    setError('')
    setMessage('')

    try {
      if (mode === 'register') {
        if (form.password !== form.confirm_password) {
          throw new Error('Passwords do not match.')
        }

        await registerUser(form)

        setMode('login')
        setMessage('Account created successfully. Please log in.')

        setForm(previous => ({
          ...previous,
          password: '',
          confirm_password: '',
        }))
      } else {
        const user = await loginUser(
          form.username,
          form.password,
        )

        onLogin(user)
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Authentication failed.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto grid min-h-[85vh] max-w-6xl
      items-center gap-12 px-6 py-12 lg:grid-cols-2">

      <section>
        <span className="rounded-full border border-orange-500/30
          bg-orange-500/10 px-4 py-2 text-sm text-orange-400">
          CODEMIND AI · PERSONALIZED LEARNING
        </span>

        <h1 className="mt-8 text-4xl font-bold leading-tight
          md:text-6xl">
          Learn to code.
          <span className="block text-orange-500">
            Your way.
          </span>
        </h1>

        <p className="mt-6 max-w-lg text-lg leading-relaxed
          text-neutral-400">
          Discover your strengths, improve your weak areas
          and follow an AI-powered 30-day learning roadmap
          designed around your skills.
        </p>

        <div className="mt-8 grid grid-cols-2 gap-4">
          {[
            ['05', 'Programming languages'],
            ['30', 'Personalized learning days'],
            ['AI', 'Adaptive assessments'],
            ['24/7', 'Learning access'],
          ].map(([value, label]) => (
            <div key={label}
              className="rounded-xl border border-neutral-800
                bg-[#191919] p-5">
              <p className="text-2xl font-bold text-orange-500">
                {value}
              </p>
              <p className="mt-1 text-sm text-neutral-400">
                {label}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-neutral-800
        bg-[#191919] p-6 md:p-8">

        <h2 className="text-2xl font-bold">
          {mode === 'login'
            ? 'Welcome back'
            : 'Create your account'}
        </h2>

        <p className="mb-6 mt-2 text-sm text-neutral-400">
          {mode === 'login'
            ? 'Continue your personalized learning journey.'
            : 'Start building your programming skills today.'}
        </p>

        {error && (
          <div role="alert"
            className="mb-4 rounded-lg border border-red-900
              bg-red-950/40 p-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {message && (
          <div role="status"
            className="mb-4 rounded-lg border border-green-900
              bg-green-950/40 p-3 text-sm text-green-300">
            {message}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">

          {mode === 'register' && (
            <div className="grid grid-cols-2 gap-3">
              <label className="learning-label">
                First name
                <input
                  className="learning-input"
                  value={form.first_name}
                  onChange={e => updateField(
                    'first_name', e.target.value)}
                  autoComplete="given-name"
                />
              </label>

              <label className="learning-label">
                Last name
                <input
                  className="learning-input"
                  value={form.last_name}
                  onChange={e => updateField(
                    'last_name', e.target.value)}
                  autoComplete="family-name"
                />
              </label>
            </div>
          )}

          <label className="learning-label">
            Username
            <input
              className="learning-input"
              value={form.username}
              onChange={e => updateField(
                'username', e.target.value)}
              autoComplete="username"
              required
            />
          </label>

          {mode === 'register' && (
            <label className="learning-label">
              Email
              <input
                className="learning-input"
                type="email"
                value={form.email}
                onChange={e => updateField(
                  'email', e.target.value)}
                autoComplete="email"
                required
              />
            </label>
          )}

          <label className="learning-label">
            Password
            <input
              className="learning-input"
              type="password"
              value={form.password}
              onChange={e => updateField(
                'password', e.target.value)}
              autoComplete={mode === 'login'
                ? 'current-password'
                : 'new-password'}
              required
            />
          </label>

          {mode === 'register' && (
            <label className="learning-label">
              Confirm password
              <input
                className="learning-input"
                type="password"
                value={form.confirm_password}
                onChange={e => updateField(
                  'confirm_password', e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>
          )}

          <button
            type="submit"
            disabled={busy}
            className="learning-primary w-full"
          >
            {busy
              ? 'Please wait...'
              : mode === 'login'
                ? 'Sign in'
                : 'Create account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-neutral-400">
          {mode === 'login'
            ? "Don't have an account? "
            : 'Already have an account? '}

          <button
            disabled={busy}
            className="font-semibold text-orange-400"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login')
              setError('')
              setMessage('')
            }}
          >
            {mode === 'login' ? 'Register' : 'Sign in'}
          </button>
        </p>
      </section>
    </div>
  )
}
