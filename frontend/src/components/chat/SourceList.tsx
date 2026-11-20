
import type { Source } from '../../types'

type Props = {
  sources: Source[]
}

export default function SourceList({ sources }: Props) {
  if (!sources.length) return null

  return (
    <div className="mt-6 overflow-hidden rounded-2xl border border-[#383838] bg-[#191919]">
      <div className="flex items-center justify-between gap-3 border-b border-[#383838] px-4 py-3">
        <span className="text-sm font-semibold text-[#f5f5f5]">
          Retrieved source files
        </span>
        <span className="text-xs text-[#a3a3a3]">
          {sources.length} sources
        </span>
      </div>

      <div className="divide-y divide-[#333333]">
        {sources.map((source, index) => (
          <details
            key={`${source.file_path}-${index}`}
            className="group"
          >
            <summary className="flex cursor-pointer list-none flex-wrap items-center gap-3 px-4 py-3 transition hover:bg-[#292929]">
              <span className="text-[#ff8a00]">{'{ }'}</span>

              <code className="min-w-0 flex-1 break-all text-xs text-[#d4d4d4]">
                {source.file_path}
              </code>

              <span className="rounded-md border border-[#383838] bg-[#202020] px-2 py-1 text-xs text-[#a3a3a3]">
                L{source.start_line}–L{source.end_line}
              </span>

              <span className="text-xs text-[#ffad42] transition group-open:rotate-180">
                ↓
              </span>
            </summary>

            <pre className="overflow-x-auto border-t border-[#333333] bg-[#111111] p-4 text-xs leading-6 text-[#d4d4d4]">
              <code>{source.content}</code>
            </pre>
          </details>
        ))}
      </div>
    </div>
  )
}
