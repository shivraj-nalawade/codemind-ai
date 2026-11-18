type Props = {
  busy: boolean
  onUploadClick: () => void
  onSuggestion: (question: string) => void
}

const suggestions = [
  {
    title: 'Explain the main functions',
    description: 'Understand the core logic in this project.',
    icon: '⌘',
  },
  {
    title: 'Where is a feature implemented?',
    description: 'Find the files responsible for a feature.',
    icon: '⌕',
  },
  {
    title: 'Summarize this repository',
    description: 'Get an overview of the project structure.',
    icon: '≡',
  },
]

export default function WelcomeScreen({
  busy,
  onUploadClick,
  onSuggestion,
}: Props) {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center px-5 py-12 sm:px-10">
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-2xl text-cyan-300">
        {'</>'}
      </div>

      <p className="mb-4 text-xs font-bold tracking-[0.24em] text-cyan-400">
        YOUR REPOSITORY, UNDERSTOOD
      </p>

      <h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-tight text-white sm:text-5xl">
        Build a deeper understanding
        <span className="block text-slate-500">of your code.</span>
      </h1>

      <p className="mt-5 max-w-2xl text-base leading-7 text-slate-400">
        Upload a code repository and ask questions in plain English.
        CodeMind AI searches your source files and uses a local language
        model to explain what it finds.
      </p>

      <div className="mt-10 grid gap-3 md:grid-cols-3">
        {suggestions.map((item) => (
          <button
            key={item.title}
            type="button"
            disabled={busy}
            onClick={() => onSuggestion(item.title)}
            className="group rounded-2xl border border-white/10 bg-white/[0.025] p-5 text-left transition hover:-translate-y-0.5 hover:border-cyan-400/30 hover:bg-cyan-400/[0.04] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span className="mb-4 flex h-9 w-9 items-center justify-center rounded-xl bg-slate-800 text-lg text-cyan-300">
              {item.icon}
            </span>
            <span className="block text-sm font-semibold text-slate-200">
              {item.title}
            </span>
            <span className="mt-2 block text-sm leading-6 text-slate-500">
              {item.description}
            </span>
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={onUploadClick}
        disabled={busy}
        className="mt-8 flex w-fit items-center gap-3 rounded-xl bg-cyan-400 px-5 py-3.5 text-sm font-bold text-slate-950 transition hover:bg-cyan-300 disabled:opacity-50"
      >
        ↑ Upload your first repository
      </button>
    </div>
  )
}