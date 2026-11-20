
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
    <aside className="hidden w-72 shrink-0 flex-col border-r border-[#303030] bg-[#191919] p-5 md:flex">

      {/* Logo */}
      <a href="/" className="mb-10 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#ff8a00] text-lg font-black text-black">
          C
        </span>

        <span className="text-xl font-semibold tracking-tight text-white">
          CodeMind <span className="text-[#ff8a00]">AI</span>
        </span>
      </a>

      {/* Workspace */}
      <p className="mb-3 px-1 text-xs font-semibold tracking-[0.18em] text-[#888888]">
        WORKSPACE
      </p>

      {/* Repository upload */}
      <label className="group mb-8 flex cursor-pointer flex-col items-start rounded-2xl border border-dashed border-[#454545] bg-[#202020] p-4 transition hover:border-[#ff8a00] hover:bg-[#292929]">

        <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[#ff8a00]/10 text-xl text-[#ff8a00]">
          ↑
        </span>

        <span className="font-semibold text-white">
          {busy ? 'Processing...' : 'Upload repository'}
        </span>

        <span className="mt-1 text-sm text-[#999999]">
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

      {/* Current project */}
      <p className="mb-3 px-1 text-xs font-semibold tracking-[0.18em] text-[#888888]">
        CURRENT PROJECT
      </p>

      {repositoryId ? (
        <div className="flex items-start gap-3 rounded-xl border border-[#333333] bg-[#202020] p-3">

          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ff8a00]/10 text-[#ff8a00]">
            {'{ }'}
          </span>

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">
              {repositoryName}
            </p>

            <p className="mt-1 text-xs text-emerald-400">
              ● Repository indexed
            </p>
          </div>
        </div>
      ) : (
        <p className="px-1 text-sm leading-6 text-[#999999]">
          Upload a ZIP to start exploring your code.
        </p>
      )}

      {/* Footer */}
      <div className="mt-auto border-t border-[#333333] pt-5">
        <p className="text-sm font-medium text-white">
          Local AI Assistant
        </p>

        <p className="mt-1 text-xs text-[#888888]">
          Powered by Ollama
        </p>
      </div>

    </aside>
  )
}
