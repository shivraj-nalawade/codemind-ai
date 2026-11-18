import { useRef, useState } from 'react'
import type { FormEvent } from 'react'

import type { Message } from './types'

import {
  uploadRepository as uploadRepositoryApi,
  parseRepository,
  buildSemanticIndex,
  askRepository,
} from './services/repositoryApi'

import Sidebar from './components/layout/Sidebar'
import Header from './components/layout/Header'
import HistorySidebar from './components/layout/HistorySidebar'
import WelcomeScreen from './components/chat/WelcomeScreen'
import MessageList from './components/chat/MessageList'
import ChatComposer from './components/chat/ChatComposer'

type HistoryItem = {
  id: string
  question: string
}

export default function App() {
  const [repositoryId, setRepositoryId] = useState('')
  const [repositoryName, setRepositoryName] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const fileInput = useRef<HTMLInputElement>(null)

  // Upload and prepare the repository.
  async function handleUpload(file?: File) {
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.zip')) {
      setError('Please select a ZIP file.')
      return
    }

    setBusy(true)
    setError('')
    setStatus('Uploading repository...')

    try {
      const uploaded = await uploadRepositoryApi(file)

      setRepositoryId(uploaded.repository_id)
      setRepositoryName(file.name.replace(/\.zip$/i, ''))
      setMessages([])
      setHistory([])
      setQuestion('')

      setStatus('Parsing source files...')
      await parseRepository(uploaded.repository_id)

      setStatus(
        'Building semantic index. The first run may take a while...',
      )
      await buildSemanticIndex(uploaded.repository_id)

      setStatus(
        `Ready! ${uploaded.file_count} files were accepted for processing.`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
      setStatus('')
    } finally {
      setBusy(false)
    }
  }

  // Send a question to the repository assistant.
  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!repositoryId || !question.trim() || busy) return

    const prompt = question.trim()

    setQuestion('')
    setError('')

    // Add the question to recent history.
    setHistory((current) => [
      {
        id: `${Date.now()}-${current.length}`,
        question: prompt,
      },
      ...current,
    ])

    setMessages((current) => [
      ...current,
      { role: 'user', content: prompt },
    ])

    setBusy(true)
    setStatus('Searching code and generating an answer...')

    try {
      const data = await askRepository(repositoryId, prompt)

      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: data.answer,
          sources: data.sources ?? [],
        },
      ])

      setStatus('')
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Question failed.',
      )
      setStatus('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-screen bg-[#17151d] text-[#f0ece6]">
      {/* Left sidebar */}
      <Sidebar
        repositoryName={repositoryName}
        repositoryId={repositoryId}
        busy={busy}
        onUpload={handleUpload}
      />

      {/* Hidden input for the welcome-screen upload button */}
      <input
        ref={fileInput}
        type="file"
        accept=".zip,application/zip"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          void handleUpload(file)
          event.target.value = ''
        }}
      />

      {/* Main workspace */}
      <section className="flex min-h-screen min-w-0 flex-1 flex-col">
        <Header repositoryName={repositoryName} />

        <section className="flex flex-1 flex-col">
          {messages.length === 0 ? (
            <WelcomeScreen
              busy={busy}
              onUploadClick={() => fileInput.current?.click()}
              onSuggestion={setQuestion}
            />
          ) : (
            <MessageList
              messages={messages}
              busy={busy}
            />
          )}
        </section>

        {/* Chat input, status and errors */}
        <ChatComposer
          question={question}
          setQuestion={setQuestion}
          onSubmit={handleAsk}
          repositoryReady={Boolean(repositoryId)}
          busy={busy}
          status={status}
          error={error}
        />
      </section>

      {/* Right history panel */}
      <HistorySidebar
        items={history}
        onSelect={setQuestion}
        onClear={() => setHistory([])}
      />
    </main>
  )
}