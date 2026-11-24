import { useEffect, useState } from 'react'
import {
  useLocation,
  useNavigate,
  Navigate,
} from 'react-router-dom'

import RepositoryWorkspace from './RepositoryWorkspace'
import LearningPortal from './features/learning/LearningPortal'

export default function App() {

  const location = useLocation()
  const navigate = useNavigate()

  // Determine the active workspace from the URL.

  const isLearning =
    location.pathname === '/learning' ||
    location.pathname.startsWith('/learning/')

  const isRepository = location.pathname === '/'

  const workspace = isLearning
    ? 'learning'
    : 'repository'

  // Keep the learning workspace mounted after opening it.

  const [learningOpened, setLearningOpened] =
    useState(isLearning)

  useEffect(() => {
    if (isLearning) {
      setLearningOpened(true)
    }
  }, [isLearning])

  // Workspace navigation.

  function openRepository() {
    navigate('/')
  }

  function openLearning() {
    if (isLearning) return

    setLearningOpened(true)
    navigate('/learning')
  }

  // Redirect unknown application URLs.

  if (!isRepository && !isLearning) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="min-h-screen bg-[#111111] text-white">

      {/* MAIN NAVIGATION */}

      <nav className="flex flex-wrap items-center
        justify-between gap-3 border-b border-neutral-800
        bg-[#191919] px-5 py-3">

        <div className="text-lg font-bold">
          CodeMind<span className="text-orange-500"> AI</span>
        </div>

        <div className="flex flex-wrap gap-2">

          {/* REPOSITORY ASSISTANT */}

          <button
            type="button"
            onClick={openRepository}
            aria-current={
              workspace === 'repository'
                ? 'page'
                : undefined
            }
            className={`rounded-lg px-4 py-2 text-sm
              font-medium transition ${
                workspace === 'repository'
                  ? 'bg-orange-500 text-black'
                  : 'text-neutral-400 hover:bg-neutral-800'
              }`}
          >
            Repository Assistant
          </button>

          {/* PERSONALIZED LEARNING */}

          <button
            type="button"
            onClick={openLearning}
            aria-current={
              workspace === 'learning'
                ? 'page'
                : undefined
            }
            className={`rounded-lg px-4 py-2 text-sm
              font-medium transition ${
                workspace === 'learning'
                  ? 'bg-orange-500 text-black'
                  : 'text-neutral-400 hover:bg-neutral-800'
              }`}
          >
            Personalized Learning
          </button>

        </div>

      </nav>

      {/* REPOSITORY WORKSPACE */}

      {/* Keep mounted to preserve existing repository
          state when switching workspaces. */}

      <div hidden={workspace !== 'repository'}>

        <RepositoryWorkspace />

      </div>

      {/* PERSONALIZED LEARNING WORKSPACE */}

      {(learningOpened || isLearning) && (

        <div hidden={workspace !== 'learning'}>

          <LearningPortal />

        </div>

      )}

    </div>
  )
}