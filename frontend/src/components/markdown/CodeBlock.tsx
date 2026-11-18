import { useState } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

type Props = {
  code: string
  language: string
}

export default function CodeBlock({ code, language }: Props) {
  const [copied, setCopied] = useState(false)

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="my-4 overflow-hidden rounded-xl border border-slate-700">
      <div className="flex items-center justify-between border-b border-slate-700 bg-slate-900 px-4 py-2">
        <span className="text-xs text-slate-400">
          {language || 'code'}
        </span>
        <button
          type="button"
          onClick={() => void copyCode()}
          className="rounded-md px-2 py-1 text-xs text-slate-300 hover:bg-slate-700 hover:text-white"
        >
          {copied ? 'Copied!' : 'Copy code'}
        </button>
      </div>

      <SyntaxHighlighter
        language={language || 'text'}
        style={oneDark}
        PreTag="div"
        customStyle={{
          margin: 0,
          padding: '16px',
          background: '#080b12',
          fontSize: '13px',
          lineHeight: '1.7',
          overflowX: 'auto',
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}