
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
    <footer className="sticky bottom-0 border-t border-[#303030] bg-[#111111]/95 px-4 pb-3 pt-4 backdrop-blur-xl sm:px-8">
      <div className="mx-auto max-w-4xl">

        {/* Processing status */}
        {status && (
          <p
            role="status"
            aria-live="polite"
            className="mb-3 text-xs text-[#a3a3a3]"
          >
            <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-[#ff8a00]" />
            {status}
          </p>
        )}

        {/* Error message */}
        {error && (
          <div
            role="alert"
            className="mb-3 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400"
          >
            {error}
          </div>
        )}

        {/* Chat form */}
        <form
          onSubmit={onSubmit}
          className="flex items-end gap-3 rounded-2xl border border-[#333333] bg-[#1b1b1b] p-3 shadow-2xl transition focus-within:border-[#ff8a00]/60"
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
            className="max-h-40 min-h-12 flex-1 resize-y bg-transparent px-2 py-2 text-sm leading-6 text-white outline-none placeholder:text-[#666666] disabled:cursor-not-allowed"
          />

          {/* Send button */}
          <button
            type="submit"
            disabled={!repositoryReady || !question.trim() || busy}
            aria-label="Send question"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#ff8a00] text-xl font-bold text-black transition hover:bg-[#e87900] disabled:cursor-not-allowed disabled:bg-[#383838] disabled:text-[#777777]"
          >
            {busy ? '…' : '↑'}
          </button>
        </form>

        {/* Footer note */}
        <p className="mt-3 text-center text-xs text-[#777777]">
          Local model · Verify AI answers against the source code.
        </p>
      </div>
    </footer>
  )
}
