
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

      {/* Main code icon */}
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-[#ff8a00]/30 bg-[#ff8a00]/10 text-2xl font-semibold text-[#ff8a00]">
        {'</>'}
      </div>

      {/* Intro label */}
      <p className="mb-4 text-xs font-bold tracking-[0.24em] text-[#ff8a00]">
        YOUR REPOSITORY, UNDERSTOOD
      </p>

      {/* Main heading */}
      <h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-tight text-white sm:text-5xl">
        Build a deeper understanding
        <span className="block text-[#ff8a00]">of your code.</span>
      </h1>

      {/* Description */}
      <p className="mt-5 max-w-2xl text-base leading-7 text-[#a3a3a3]">
        Upload a code repository and ask questions in plain English.
        CodeMind AI searches your source files and uses a local language
        model to explain what it finds.
      </p>

      {/* Suggestion cards */}
      <div className="mt-10 grid gap-3 md:grid-cols-3">
        {suggestions.map((item) => (
          <button
            key={item.title}
            type="button"
            disabled={busy}
            onClick={() => onSuggestion(item.title)}
            className="group rounded-2xl border border-[#333333] bg-[#1b1b1b] p-5 text-left transition duration-200 hover:-translate-y-1 hover:border-[#ff8a00]/60 hover:bg-[#242424] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl border border-[#ff8a00]/20 bg-[#ff8a00]/10 text-xl text-[#ff8a00] transition group-hover:bg-[#ff8a00] group-hover:text-black">
              {item.icon}
            </span>

            <span className="block text-sm font-semibold text-white">
              {item.title}
            </span>

            <span className="mt-2 block text-sm leading-6 text-[#999999]">
              {item.description}
            </span>
          </button>
        ))}
      </div>

      {/* Upload button */}
      <button
        type="button"
        onClick={onUploadClick}
        disabled={busy}
        className="mt-8 flex w-fit items-center gap-3 rounded-xl bg-[#ff8a00] px-5 py-3.5 text-sm font-bold text-black transition hover:bg-[#e87900] disabled:cursor-not-allowed disabled:opacity-50"
      >
        ↑ Upload your first repository
      </button>
    </div>
  )
}
