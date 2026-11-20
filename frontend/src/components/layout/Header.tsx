
type Props = {
  repositoryName: string
}

export default function Header({ repositoryName }: Props) {
  return (
    <header className="sticky top-0 z-10 flex min-h-[72px] items-center justify-between gap-3 border-b border-[#303030] bg-[#111111]/95 px-4 backdrop-blur-xl sm:px-8">

      {/* Workspace breadcrumb */}
      <div className="flex min-w-0 items-center gap-2 text-sm">
        <span className="text-[#888888]">
          Workspace
        </span>

        <span className="text-[#555555]">/</span>

        <span className="truncate font-medium text-white">
          {repositoryName || 'New conversation'}
        </span>
      </div>

      {/* Local model indicator */}
      <div className="flex shrink-0 items-center gap-2 rounded-full border border-[#ff8a00]/30 bg-[#ff8a00]/10 px-3 py-2 text-xs text-[#ffad42]">

        <span className="h-1.5 w-1.5 rounded-full bg-[#ff8a00]" />

        <span className="hidden sm:inline">
          Qwen2.5-Coder 3B
        </span>

        <span className="sm:hidden">
          Local AI
        </span>
      </div>

    </header>
  )
}
