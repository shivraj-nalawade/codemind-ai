import type { ChangeEvent } from 'react'

type Props = {
  repositoryName: string
  repositoryId: string
  busy: boolean
  onUpload: (file?: File) => void
}

export default function Sidebar({
  repositoryName,
  repositoryId,
  busy,
  onUpload,
}: Props) {
  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    void onUpload(file)
    event.target.value = ''
  }

  return (
    <aside className="hidden w-72 shrink-0 flex-col border-r border-white/10 bg-[#0d121e] p-5 md:flex">
      <a href="/" className="mb-10 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400 text-lg font-black text-slate-950">
          C
        </span>
        <span className="text-xl font-semibold tracking-tight">
          CodeMind <span className="text-cyan-400">AI</span>
        </span>
      </a>

      <p className="mb-3 px-1 text-xs font-semibold tracking-[0.18em] text-slate-500">
        WORKSPACE
      </p>

      <label className="group mb-8 flex cursor-pointer flex-col items-start rounded-2xl border border-dashed border-slate-700 bg-slate-900/60 p-4 transition hover:border-cyan-400/60 hover:bg-cyan-400/5">
        <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/10 text-xl text-cyan-300">
          ↑
        </span>
        <span className="font-semibold">
          {busy ? 'Processing...' : 'Upload repository'}
        </span>
        <span className="mt-1 text-sm text-slate-500">
          Choose a project ZIP file
        </span>
        <input
          type="file"
          accept=".zip,application/zip"
          disabled={busy}
          className="hidden"
          onChange={handleFileChange}
        />
      </label>

      <p className="mb-3 px-1 text-xs font-semibold tracking-[0.18em] text-slate-500">
        CURRENT PROJECT
      </p>

      {repositoryId ? (
        <div className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-400/10 text-violet-300">
            {'{ }'}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{repositoryName}</p>
            <p className="mt-1 text-xs text-emerald-400">
              ● Repository indexed
            </p>
          </div>
        </div>
      ) : (
        <p className="px-1 text-sm leading-6 text-slate-500">
          Upload a ZIP to start exploring your code.
        </p>
      )}

      <div className="mt-auto border-t border-white/10 pt-5">
        <p className="text-sm font-medium">Local AI Assistant</p>
        <p className="mt-1 text-xs text-slate-500">Powered by Ollama</p>
      </div>
    </aside>
  )
}