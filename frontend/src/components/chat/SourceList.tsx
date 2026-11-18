import type { Source } from '../../types'

type Props = {
  sources: Source[]
}

export default function SourceList({ sources }: Props) {
  if (!sources.length) return null

  return (
    <div className="mt-6 overflow-hidden rounded-2xl border border-white/10 bg-[#0d121e]">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
        <span className="text-sm font-semibold text-slate-200">
          Retrieved source files
        </span>
        <span className="text-xs text-slate-500">
          {sources.length} sources
        </span>
      </div>

      <div className="divide-y divide-white/[0.07]">
        {sources.map((source, index) => (
          <details
            key={`${source.file_path}-${index}`}
            className="group"
          >
            <summary className="flex cursor-pointer list-none flex-wrap items-center gap-3 px-4 py-3 hover:bg-white/[0.03]">
              <span className="text-cyan-300">{'{ }'}</span>
              <code className="min-w-0 flex-1 break-all text-xs text-slate-300">
                {source.file_path}
              </code>
              <span className="rounded-md bg-slate-800 px-2 py-1 text-xs text-slate-400">
                L{source.start_line}–L{source.end_line}
              </span>
              <span className="text-xs text-slate-500 group-open:rotate-180">
                ↓
              </span>
            </summary>

            <pre className="overflow-x-auto border-t border-white/5 bg-[#080b12] p-4 text-xs leading-6 text-emerald-200">
              <code>{source.content}</code>
            </pre>
          </details>
        ))}
      </div>
    </div>
  )
}