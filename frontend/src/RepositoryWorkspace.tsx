import { useEffect, useRef, useState } from 'react'

import type { FormEvent } from 'react'

import type { Message } from './types'

import {
  uploadRepository as uploadRepositoryApi,
  parseRepository,
  buildSemanticIndex,
  askRepository,
  getRepositoryStatus,
} from './services/repositoryApi'

import {
  loadRepositoryWorkspace,
  saveRepositoryWorkspace,
  clearRepositoryWorkspace,
} from './services/repositoryStorage'

import type {
  HistoryItem,
} from './services/repositoryStorage'

import Sidebar from './components/layout/Sidebar'
import Header from './components/layout/Header'
import HistorySidebar from './components/layout/HistorySidebar'
import WelcomeScreen from './components/chat/WelcomeScreen'
import MessageList from './components/chat/MessageList'
import ChatComposer from './components/chat/ChatComposer'


export default function RepositoryWorkspace() {

  // ========================================================
  // WORKSPACE STATE
  // ========================================================

  const [repositoryId, setRepositoryId] = useState('')

  const [repositoryName, setRepositoryName] = useState('')

  const [messages, setMessages] = useState<Message[]>([])

  const [question, setQuestion] = useState('')

  const [history, setHistory] = useState<HistoryItem[]>([])

  const [busy, setBusy] = useState(false)

  const [status, setStatus] = useState('')

  const [error, setError] = useState('')

  const [repositoryReady, setRepositoryReady] =
    useState(false)

  const [restoring, setRestoring] = useState(true)

  const [restoreFailed, setRestoreFailed] =
    useState(false)

  const [storageWarning, setStorageWarning] =
    useState('')

  const fileInput = useRef<HTMLInputElement>(null)


  // ========================================================
  // RESTORE WORKSPACE AFTER PAGE REFRESH
  // ========================================================

  useEffect(() => {

    let cancelled = false

    async function restoreWorkspace() {

      const saved = loadRepositoryWorkspace()

      if (!saved || !saved.repositoryId) {

        if (!cancelled) {
          setRestoring(false)
        }

        return
      }

      try {

        const repositoryStatus =
          await getRepositoryStatus(saved.repositoryId)

        if (cancelled) return

        // Session expired or repository no longer exists.
        if (!repositoryStatus) {

          clearRepositoryWorkspace()

          setError(
            'Repository session expired. ' +
            'Please upload your repository again.',
          )

          return
        }

        // Restore saved repository information.
        setRepositoryId(saved.repositoryId)

        setRepositoryName(saved.repositoryName)

        setMessages(saved.messages)

        setQuestion(saved.question)

        setHistory(saved.history)

        setRepositoryReady(repositoryStatus.ready)

        // Never mark an incomplete repository as ready.
        if (!repositoryStatus.ready) {

          setError(
            'Repository preparation was incomplete. ' +
            'Please upload your repository again.',
          )

        } else {

          setStatus('')

        }

      } catch (err) {

        if (cancelled) return

        // Preserve saved data if the backend is temporarily
        // unavailable instead of deleting the conversation.
        setRestoreFailed(true)

        setError(
          err instanceof Error
            ? err.message
            : 'Could not restore repository workspace.',
        )

      } finally {

        if (!cancelled) {
          setRestoring(false)
        }

      }
    }

    void restoreWorkspace()

    return () => {
      cancelled = true
    }

  }, [])


  // ========================================================
  // AUTOMATICALLY SAVE WORKSPACE
  // ========================================================

  useEffect(() => {

    // Do not overwrite saved data during restoration.
    if (restoring || restoreFailed) return

    if (!repositoryId) return

    const saved = saveRepositoryWorkspace({
      repositoryId,
      repositoryName,
      messages,
      question,
      history,
      repositoryReady,
      updatedAt: new Date().toISOString(),
    })

    if (!saved) {

      setStorageWarning(
        'Browser storage is unavailable or full. ' +
        'Recent conversation changes may not survive refresh.',
      )

    } else {

      setStorageWarning('')

    }

  }, [
    repositoryId,
    repositoryName,
    messages,
    question,
    history,
    repositoryReady,
    restoring,
    restoreFailed,
  ])


  // ========================================================
  // UPLOAD AND PREPARE REPOSITORY
  // ========================================================

  async function handleUpload(file?: File) {

    if (!file || busy || restoring) return

    if (!file.name.toLowerCase().endsWith('.zip')) {

      setError('Please select a ZIP file.')

      return
    }

    setBusy(true)

    setError('')

    setStatus('Uploading repository...')

    try {

      const uploaded = await uploadRepositoryApi(file)

      // Replace the previous workspace only after
      // the new repository upload succeeds.
      setRestoreFailed(false)

      setRepositoryReady(false)

      setRepositoryId(uploaded.repository_id)

      setRepositoryName(
        file.name.replace(/\.zip$/i, ''),
      )

      setMessages([])

      setHistory([])

      setQuestion('')

      // Parse repository.
      setStatus('Parsing source files...')

      await parseRepository(
        uploaded.repository_id,
      )

      // Build semantic index.
      setStatus(
        'Building semantic index. ' +
        'The first run may take a while...',
      )

      await buildSemanticIndex(
        uploaded.repository_id,
      )

      // Enable questions only after preparation succeeds.
      setRepositoryReady(true)

      setStatus(
        `Ready! ${uploaded.file_count} files ` +
        'were accepted for processing.',
      )

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : 'Upload failed.',
      )

      setStatus('')

    } finally {

      setBusy(false)

    }
  }


  // ========================================================
  // ASK REPOSITORY QUESTION
  // ========================================================

  async function handleAsk(
    event: FormEvent<HTMLFormElement>,
  ) {

    event.preventDefault()

    if (
      !repositoryId ||
      !repositoryReady ||
      !question.trim() ||
      busy ||
      restoring
    ) {
      return
    }

    const prompt = question.trim()

    setQuestion('')

    setError('')

    // Add question to recent history.
    setHistory((current) => [
      {
        id: `${Date.now()}-${current.length}`,
        question: prompt,
      },
      ...current,
    ])

    // Add user message.
    setMessages((current) => [
      ...current,
      {
        role: 'user',
        content: prompt,
      },
    ])

    setBusy(true)

    setStatus(
      'Searching code and generating an answer...',
    )

    try {

      const data = await askRepository(
        repositoryId,
        prompt,
      )

      // Add assistant answer and source citations.
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
        err instanceof Error
          ? err.message
          : 'Question failed.',
      )

      setStatus('')

    } finally {

      setBusy(false)

    }
  }


  // ========================================================
  // RESTORATION LOADING SCREEN
  // ========================================================

  if (restoring) {

    return (
      <div
        className="flex min-h-screen items-center
          justify-center bg-[#111111] text-white"
      >
        <div className="text-center">

          <div
            className="mx-auto mb-4 h-10 w-10
              animate-spin rounded-full border-4
              border-neutral-700 border-t-orange-500"
          />

          <h2 className="text-lg font-semibold">
            Restoring workspace
          </h2>

          <p className="mt-2 text-sm text-neutral-400">
            Loading your repository and conversation...
          </p>

        </div>
      </div>
    )
  }


  // ========================================================
  // MAIN WORKSPACE
  // ========================================================

  return (

    <main
      className="flex min-h-screen
        bg-[#111111] text-[#f5f5f5]"
    >

      {/* LEFT SIDEBAR */}

      <Sidebar
        repositoryName={repositoryName}
        repositoryId={repositoryId}
        busy={busy}
        onUpload={handleUpload}
      />


      {/* HIDDEN ZIP FILE INPUT */}

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


      {/* MAIN WORKSPACE */}

      <section
        className="flex min-h-screen min-w-0
          flex-1 flex-col"
      >

        <Header
          repositoryName={repositoryName}
        />


        {/* RESTORATION ERROR */}

        {restoreFailed && (

          <div
            className="mx-5 mt-4 rounded-lg border
              border-red-900 bg-red-950/30 p-4"
          >

            <p className="text-sm text-red-300">
              Your saved workspace could not be restored.
              Make sure the backend is running.
            </p>

            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-3 rounded-lg bg-orange-500
                px-4 py-2 text-sm font-medium text-black
                hover:bg-orange-400"
            >
              Retry restoration
            </button>

          </div>

        )}


        {/* BROWSER STORAGE WARNING */}

        {storageWarning && (

          <div
            className="mx-5 mt-4 rounded-lg border
              border-yellow-900 bg-yellow-950/30
              p-3 text-sm text-yellow-300"
          >
            {storageWarning}
          </div>

        )}


        {/* CHAT CONTENT */}

        <section className="flex flex-1 flex-col">

          {messages.length === 0 ? (

            <WelcomeScreen
              busy={busy}
              onUploadClick={() =>
                fileInput.current?.click()
              }
              onSuggestion={setQuestion}
            />

          ) : (

            <MessageList
              messages={messages}
              busy={busy}
            />

          )}

        </section>


        {/* CHAT COMPOSER */}

        <ChatComposer
          question={question}
          setQuestion={setQuestion}
          onSubmit={handleAsk}
          repositoryReady={repositoryReady}
          busy={busy}
          status={status}
          error={error}
        />

      </section>


      {/* RIGHT HISTORY PANEL */}

      <HistorySidebar
        items={history}
        onSelect={setQuestion}
        onClear={() => setHistory([])}
      />

    </main>

  )
}