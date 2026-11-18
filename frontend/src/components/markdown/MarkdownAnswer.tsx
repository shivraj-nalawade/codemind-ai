import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CodeBlock from './CodeBlock'

type Props = {
  content: string
}

export default function MarkdownAnswer({ content }: Props) {
  return (
    <div className="min-w-0 text-sm leading-7 text-slate-300">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-4 mt-6 text-2xl font-bold text-white">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-3 mt-6 text-xl font-semibold text-white">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-5 text-lg font-semibold text-white">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="mb-3 whitespace-pre-wrap">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="mb-4 ml-5 list-disc space-y-1">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-4 ml-5 list-decimal space-y-1">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="pl-1">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-white">
              {children}
            </strong>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-4 border-l-2 border-cyan-400 pl-4 text-slate-400">
              {children}
            </blockquote>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-cyan-300 underline underline-offset-4 hover:text-cyan-200"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto rounded-lg border border-slate-700">
              <table className="w-full border-collapse text-left text-sm">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-slate-700 bg-slate-800 px-3 py-2 text-white">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-slate-800 px-3 py-2">
              {children}
            </td>
          ),
          code: ({ children, className }) => {
            const match = /language-([\w-]+)/.exec(className || '')
            const code = String(children).replace(/\n$/, '')

            if (match || code.includes('\n')) {
              return (
                <CodeBlock
                  code={code}
                  language={match?.[1] || 'text'}
                />
              )
            }

            return (
              <code className="rounded-md border border-slate-700 bg-slate-800 px-1.5 py-0.5 font-mono text-cyan-200">
                {children}
              </code>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}