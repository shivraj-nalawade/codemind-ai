
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
    <div className="my-4 overflow-hidden rounded-xl border border-[#383838]">

      {/* Code header */}
      <div className="flex items-center justify-between border-b border-[#383838] bg-[#202020] px-4 py-2">
        <span className="text-xs font-medium text-[#ffad42]">
          {language || 'code'}
        </span>

        <button
          type="button"
          onClick={() => void copyCode()}
          className="rounded-md border border-[#444444] px-2 py-1 text-xs text-[#aaaaaa] transition hover:border-[#ff8a00]/50 hover:bg-[#292929] hover:text-[#ffad42]"
        >
          {copied ? 'Copied!' : 'Copy code'}
        </button>
      </div>

      {/* Syntax highlighted code */}
      <SyntaxHighlighter
        language={language || 'text'}
        style={oneDark}
        PreTag="div"
        customStyle={{
          margin: 0,
          padding: '16px',
          background: '#141414',
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
