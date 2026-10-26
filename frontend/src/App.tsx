import { useCallback, useEffect, useState } from 'react'
import './App.css'

type QuestionStatus = 'new' | 'pinned' | 'answered' | 'skipped'

interface Topic {
  id: string
  title: string
  summary: string
  message_count: number
}

interface QuestionGroup {
  id: string
  representative_question: string
  unique_viewer_count: number
  priority_score: number
  status: QuestionStatus
}

interface DashboardState {
  messages: unknown[]
  topics: Topic[]
  questions: QuestionGroup[]
  spotlight: {
    question_id: string | null
    question_text: string | null
    viewer_count: number
  }
  updated_at: string
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const emptyState: DashboardState = {
  messages: [], topics: [], questions: [],
  spotlight: { question_id: null, question_text: null, viewer_count: 0 },
  updated_at: new Date().toISOString(),
}

function App() {
  const [state, setState] = useState<DashboardState>(emptyState)
  const [isLoading, setIsLoading] = useState(true)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const request = useCallback(async (path: string, options?: RequestInit) => {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      headers: { 'Content-Type': 'application/json' }, ...options,
    })
    if (!response.ok) throw new Error(`Request failed (${response.status})`)
    return (await response.json()) as DashboardState
  }, [])

  useEffect(() => {
    request('/api/state').then(setState)
      .catch(() => setError('Backend is offline. Start FastAPI on port 8000.'))
      .finally(() => setIsLoading(false))
  }, [request])

  const runSimulation = async (scenario: string) => {
    setBusyAction(`simulate-${scenario}`); setError(null)
    try {
      setState(await request('/api/dev/simulate', {
        method: 'POST', body: JSON.stringify({ scenario }),
      }))
    } catch { setError('Could not load the demo conversation.') }
    finally { setBusyAction(null) }
  }

  const updateQuestion = async (questionId: string, action: QuestionStatus) => {
    setBusyAction(`${questionId}-${action}`); setError(null)
    try { setState(await request(`/api/questions/${questionId}/${action}`, { method: 'POST' })) }
    catch { setError('Could not update the question.') }
    finally { setBusyAction(null) }
  }

  const clearSpotlight = async () => {
    setBusyAction('clear'); setError(null)
    try { setState(await request('/api/spotlight', { method: 'DELETE' })) }
    catch { setError('Could not clear the spotlight.') }
    finally { setBusyAction(null) }
  }

  const activeQuestions = state.questions.filter((q) => q.status === 'new' || q.status === 'pinned')

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span /></div>
          <div><strong>ChatPulse</strong><span>Audience intelligence</span></div>
        </div>
        <div className="stream-status">
          <div className="channel-avatar">CP</div>
          <div><span className="eyebrow">DEMO CHANNEL</span><strong>ChatPulse Live</strong></div>
          <span className={`status-dot ${error ? 'offline' : ''}`} />
          <span className="connection-label">{error ? 'Offline' : 'Connected'}</span>
        </div>
      </header>

      <section className="control-strip" aria-label="Demo controls">
        <div><span className="live-pulse" /><strong>{state.messages.length} messages</strong><span>in the current analysis window</span></div>
        <div className="scenario-buttons">
          <span>Simulate:</span>
          {['mixed', 'questions', 'quiet'].map((scenario) => (
            <button className="ghost-button" disabled={busyAction !== null} key={scenario}
              onClick={() => runSimulation(scenario)} type="button">
              {busyAction === `simulate-${scenario}` ? 'Loading…' : scenario}
            </button>
          ))}
        </div>
      </section>
      {error && <div className="error-banner" role="alert">{error}</div>}

      <main className="dashboard-grid">
        <section className="panel topic-panel">
          <PanelHeading eyebrow="LIVE ANALYSIS" title="Topic radar" subtitle="What your audience is talking about" icon="⌁" />
          <div className="panel-content topic-list">
            {isLoading ? <EmptyState title="Connecting…" copy="Reading the latest audience state." />
              : state.topics.length === 0 ? <EmptyState title="No topics yet" copy="Run a simulation to fill the radar." />
              : state.topics.map((topic, index) => (
                <article className="topic-card" key={topic.id}>
                  <div className="topic-rank">0{index + 1}</div>
                  <div><h3>{topic.title}</h3><p>{topic.summary}</p>
                    <div className="card-meta"><span>{topic.message_count} messages</span><span>updated now</span></div>
                  </div>
                </article>
              ))}
          </div>
        </section>

        <section className="panel question-panel">
          <PanelHeading eyebrow="PRIORITIZED" title="Question queue" subtitle="Grouped by intent and audience interest" icon="?" count={activeQuestions.length} />
          <div className="panel-content question-list">
            {isLoading ? <EmptyState title="Finding questions…" copy="The queue will update after analysis." />
              : activeQuestions.length === 0 ? <EmptyState title="No questions detected" copy="Try the mixed or questions simulation." />
              : activeQuestions.map((question) => (
                <article className={`question-card ${question.status === 'pinned' ? 'is-pinned' : ''}`} key={question.id}>
                  <div className="question-topline">
                    <span className="viewer-count">{question.unique_viewer_count} {question.unique_viewer_count === 1 ? 'viewer' : 'viewers'}</span>
                    <span className="score">{Math.round(question.priority_score * 100)} priority</span>
                  </div>
                  <h3>{question.representative_question}</h3>
                  <div className="question-actions">
                    <button className="primary-button" disabled={busyAction !== null}
                      onClick={() => updateQuestion(question.id, 'pinned')} type="button">
                      {question.status === 'pinned' ? 'On spotlight' : 'Pin to spotlight'}
                    </button>
                    <button className="icon-button success" aria-label="Mark answered" disabled={busyAction !== null}
                      onClick={() => updateQuestion(question.id, 'answered')} title="Mark answered" type="button">✓</button>
                    <button className="icon-button" aria-label="Skip question" disabled={busyAction !== null}
                      onClick={() => updateQuestion(question.id, 'skipped')} title="Skip question" type="button">×</button>
                  </div>
                </article>
              ))}
          </div>
        </section>

        <section className="panel spotlight-panel">
          <PanelHeading eyebrow="OBS OUTPUT" title="Live spotlight" subtitle="Preview what viewers see on stream" icon="◉" />
          <div className="panel-content spotlight-content">
            <div className={`overlay-preview ${state.spotlight.question_id ? 'is-live' : ''}`}>
              <div className="preview-grid" />
              {state.spotlight.question_text ? (
                <div className="spotlight-card"><span>CHATPULSE · AUDIENCE SPOTLIGHT</span>
                  <blockquote>“{state.spotlight.question_text}”</blockquote>
                  <p>{state.spotlight.viewer_count} viewers are asking</p>
                </div>
              ) : (
                <div className="empty-preview"><div className="preview-icon">◈</div><strong>Spotlight is clear</strong><span>Pin a question to preview it here</span></div>
              )}
            </div>
            <div className="spotlight-footer">
              <div><span className={state.spotlight.question_id ? 'on-air-dot' : 'idle-dot'} /><span>{state.spotlight.question_id ? 'Live on overlay' : 'Overlay ready'}</span></div>
              <button className="danger-button" disabled={!state.spotlight.question_id || busyAction !== null}
                onClick={clearSpotlight} type="button">Clear spotlight</button>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

function PanelHeading({ eyebrow, title, subtitle, icon, count }: { eyebrow: string; title: string; subtitle: string; icon: string; count?: number }) {
  return <header className="panel-heading"><div className="panel-icon" aria-hidden="true">{icon}</div><div>
    <span className="eyebrow">{eyebrow}</span><h2>{title} {count !== undefined && <small>{count}</small>}</h2><p>{subtitle}</p>
  </div></header>
}

function EmptyState({ title, copy }: { title: string; copy: string }) {
  return <div className="empty-state"><div>⌁</div><strong>{title}</strong><span>{copy}</span></div>
}

export default App

