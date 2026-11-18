type Props = {
  repositoryName: string
}

export default function Header({ repositoryName }: Props) {
  return (
    <header className="sticky top-0 z-10 flex min-h-[72px] items-center justify-between gap-3 border-b border-white/10 bg-[#090d16]/90 px-4 backdrop-blur-xl sm:px-8">
      <div className="flex min-w-0 items-center gap-2 text-sm">
        <span className="text-slate-500">Workspace</span>
        <span className="text-slate-700">/</span>
        <span className="truncate font-medium text-slate-200">
          {repositoryName || 'New conversation'}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/5 px-3 py-2 text-xs text-emerald-300">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        <span className="hidden sm:inline">Qwen2.5-Coder 3B</span>
        <span className="sm:hidden">Local AI</span>
      </div>
    </header>
  )
}