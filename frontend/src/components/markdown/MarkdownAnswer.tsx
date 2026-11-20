
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CodeBlock from './CodeBlock'

type Props = {
  content: string
}

export default function MarkdownAnswer({ content }: Props) {
  return (
    <div className="min-w-0 text-sm leading-7 text-[#d4d4d4]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-4 mt-6 text-2xl font-bold text-[#f5f5f5]">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-3 mt-6 text-xl font-semibold text-[#f5f5f5]">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-5 text-lg font-semibold text-[#f5f5f5]">
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
            <strong className="font-semibold text-[#ffffff]">
              {children}
            </strong>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-4 border-l-2 border-[#ff8a00] pl-4 text-[#a3a3a3]">
              {children}
            </blockquote>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-[#ffad42] underline underline-offset-4 hover:text-[#ff8a00]"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto rounded-lg border border-[#383838]">
              <table className="w-full border-collapse text-left text-sm">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-[#383838] bg-[#202020] px-3 py-2 text-[#f5f5f5]">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-[#303030] px-3 py-2">
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
              <code className="rounded-md border border-[#383838] bg-[#202020] px-1.5 py-0.5 font-mono text-[#ffad42]">
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
