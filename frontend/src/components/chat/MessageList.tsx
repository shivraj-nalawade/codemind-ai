
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
          {/* Message avatar */}
          <div
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${
              message.role === 'user'
                ? 'border border-[#444444] bg-[#292929] text-white'
                : 'border border-[#ff8a00]/30 bg-[#ff8a00]/10 text-[#ff8a00]'
            }`}
          >
            {message.role === 'user' ? 'Y' : 'C'}
          </div>

          <div className="min-w-0 flex-1 pt-1">
            {/* Sender name */}
            <p className="mb-3 text-sm font-semibold text-white">
              {message.role === 'user' ? 'You' : 'CodeMind AI'}
            </p>

            {/* Message content */}
            {message.role === 'assistant' ? (
              <MarkdownAnswer content={message.content} />
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-7 text-[#d4d4d4]">
                {message.content}
              </p>
            )}

            {/* Retrieved source files */}
            {message.role === 'assistant' && message.sources && (
              <SourceList sources={message.sources} />
            )}
          </div>
        </article>
      ))}

      {/* AI thinking indicator */}
      {busy && (
        <div className="flex items-center gap-3 pl-1 text-sm text-[#a3a3a3]">
          <span className="flex gap-1">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#ff8a00]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#ff8a00] [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#ff8a00] [animation-delay:300ms]" />
          </span>
          Thinking...
        </div>
      )}
    </div>
  )
}
