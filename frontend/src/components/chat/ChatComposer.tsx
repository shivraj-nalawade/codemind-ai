import type { FormEvent, KeyboardEvent } from 'react'

type Props = {
  question: string
  setQuestion: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  repositoryReady: boolean
  busy: boolean
  status: string
  error: string
}

export default function ChatComposer({
  question,
  setQuestion,
  onSubmit,
  repositoryReady,
  busy,
  status,
  error,
}: Props) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <footer className="sticky bottom-0 border-t border-white/10 bg-[#090d16]/95 px-4 pb-3 pt-4 backdrop-blur-xl sm:px-8">
      <div className="mx-auto max-w-4xl">
        {status && (
          <p role="status" aria-live="polite" className="mb-3 text-xs text-slate-400">
            <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-cyan-400" />
            {status}
          </p>
        )}

        {error && (
          <div role="alert" className="mb-3 rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <form
          onSubmit={onSubmit}
          className="flex items-end gap-3 rounded-2xl border border-white/10 bg-[#111725] p-3 shadow-2xl transition focus-within:border-cyan-400/30"
        >
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              repositoryReady
                ? 'Ask anything about your code...'
                : 'Upload a repository to start asking questions'
            }
            disabled={!repositoryReady || busy}
            rows={2}
            className="max-h-40 min-h-12 flex-1 resize-y bg-transparent px-2 py-2 text-sm leading-6 text-slate-100 outline-none placeholder:text-slate-600 disabled:cursor-not-allowed"
          />

          <button
            type="submit"
            disabled={!repositoryReady || !question.trim() || busy}
            aria-label="Send question"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-cyan-400 text-xl font-bold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {busy ? '…' : '↑'}
          </button>
        </form>

        <p className="mt-3 text-center text-xs text-slate-600">
          Local model · Verify AI answers against the source code.
        </p>
      </div>
    </footer>
  )
}