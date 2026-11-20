
type HistoryItem = {
  id: string
  question: string
}

type Props = {
  items: HistoryItem[]
  onSelect: (question: string) => void
  onClear: () => void
}

export default function HistorySidebar({
  items,
  onSelect,
  onClear,
}: Props) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-l border-[#303030] bg-[#191919] p-5 xl:flex">

      {/* Sidebar heading */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">
            Recent questions
          </h2>

          <p className="mt-1 text-xs text-[#888888]">
            This session
          </p>
        </div>

        <span className="rounded-full border border-[#ff8a00]/20 bg-[#ff8a00]/10 px-2 py-1 text-xs text-[#ffad42]">
          {items.length}
        </span>
      </div>

      {/* Question history */}
      <div className="flex-1 space-y-2 overflow-y-auto">
        {items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[#444444] bg-[#202020] p-4">
            <p className="text-sm leading-6 text-[#999999]">
              Your recent questions will appear here.
            </p>
          </div>
        ) : (
          items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.question)}
              className="w-full rounded-xl border border-transparent p-3 text-left transition hover:border-[#ff8a00]/30 hover:bg-[#242424]"
            >
              <span className="mb-2 block text-xs font-semibold tracking-wide text-[#ff8a00]">
                CODE QUESTION
              </span>

              <span className="line-clamp-3 block text-sm leading-5 text-[#eeeeee]">
                {item.question}
              </span>
            </button>
          ))
        )}
      </div>

      {/* Clear history */}
      <button
        type="button"
        onClick={onClear}
        disabled={items.length === 0}
        className="mt-5 rounded-xl border border-[#444444] px-3 py-2.5 text-sm text-[#aaaaaa] transition hover:border-[#ff8a00]/50 hover:text-[#ff8a00] disabled:cursor-not-allowed disabled:opacity-40"
      >
        Clear history
      </button>

      {/* Footer */}
      <p className="mt-3 text-center text-xs text-[#777777]">
        History is kept in this session only.
      </p>
    </aside>
  )
}
