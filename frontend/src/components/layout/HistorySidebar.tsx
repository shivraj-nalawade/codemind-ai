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
    <aside className="hidden w-64 shrink-0 flex-col border-l border-[#393342] bg-[#211d29] p-5 xl:flex">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-[#f0ece6]">
            Recent questions
          </h2>
          <p className="mt-1 text-xs text-[#aaa4b5]">
            This session
          </p>
        </div>

        <span className="rounded-full bg-[#302a3a] px-2 py-1 text-xs text-[#b5a0e8]">
          {items.length}
        </span>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto">
        {items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[#51485d] p-4">
            <p className="text-sm text-[#aaa4b5]">
              Your recent questions will appear here.
            </p>
          </div>
        ) : (
          items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.question)}
              className="w-full rounded-xl border border-transparent p-3 text-left transition hover:border-[#51485d] hover:bg-[#302a3a]"
            >
              <span className="mb-2 block text-xs text-[#77b8a8]">
                CODE QUESTION
              </span>
              <span className="line-clamp-3 block text-sm leading-5 text-[#f0ece6]">
                {item.question}
              </span>
            </button>
          ))
        )}
      </div>

      <button
        type="button"
        onClick={onClear}
        disabled={items.length === 0}
        className="mt-5 rounded-xl border border-[#51485d] px-3 py-2.5 text-sm text-[#aaa4b5] transition hover:border-[#e58b72]/50 hover:text-[#e58b72] disabled:opacity-40"
      >
        Clear history
      </button>

      <p className="mt-3 text-center text-xs text-[#777080]">
        History is kept in this session only.
      </p>
    </aside>
  )
}