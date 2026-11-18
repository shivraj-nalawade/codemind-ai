import type { Message } from '../../types'
import MarkdownAnswer from '../markdown/MarkdownAnswer'
import SourceList from './SourceList'

type Props = {
  messages: Message[]
  busy: boolean
}

export default function MessageList({ messages, busy }: Props) {
  return (
    <div className="mx-auto w-full max-w-4xl flex-1 space-y-8 px-4 py-8 sm:px-8">
      {messages.map((message, index) => (
        <article
          key={`${message.role}-${index}`}
          className="flex items-start gap-3 sm:gap-4"
        >
          <div
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${
              message.role === 'user'
                ? 'bg-slate-700 text-white'
                : 'border border-cyan-400/20 bg-cyan-400/10 text-cyan-300'
            }`}
          >
            {message.role === 'user' ? 'Y' : 'C'}
          </div>

          <div className="min-w-0 flex-1 pt-1">
            <p className="mb-3 text-sm font-semibold text-slate-200">
              {message.role === 'user' ? 'You' : 'CodeMind AI'}
            </p>

            {message.role === 'assistant' ? (
              <MarkdownAnswer content={message.content} />
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
                {message.content}
              </p>
            )}

            {message.role === 'assistant' && message.sources && (
              <SourceList sources={message.sources} />
            )}
          </div>
        </article>
      ))}

      {busy && (
        <div className="flex items-center gap-3 pl-1 text-sm text-slate-400">
          <span className="flex gap-1">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400 [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400 [animation-delay:300ms]" />
          </span>
          Thinking...
        </div>
      )}
    </div>
  )
}