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

interface ChatMessage {
  id: string
  display_name: string
  text: string
}

interface AuthStatus {
  configured: boolean
  status: 'ready' | 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'authentication_required'
  channel_login: string | null
  channel_name: string | null
  stream: {
    id: string
    title: string
    game_name: string
    viewer_count: number
    started_at: string
  } | null
  tracking: boolean
  error: string | null
}

interface DashboardState {
  messages: ChatMessage[]
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
const emptyAuth: AuthStatus = {
  configured: false, status: 'authentication_required', channel_login: null, channel_name: null,
  stream: null, tracking: false, error: null,
}

function App() {
  const [state, setState] = useState<DashboardState>(emptyState)
  const [isLoading, setIsLoading] = useState(true)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [auth, setAuth] = useState<AuthStatus>(emptyAuth)

  const request = useCallback(async (path: string, options?: RequestInit) => {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      headers: { 'Content-Type': 'application/json' }, ...options,
    })
    if (!response.ok) throw new Error(`Request failed (${response.status})`)
    return (await response.json()) as DashboardState
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [nextState, nextAuth] = await Promise.all([
        request('/api/state'),
        fetch(`${apiBaseUrl}/api/auth/status`).then((response) => {
          if (!response.ok) throw new Error(`Request failed (${response.status})`)
          return response.json() as Promise<AuthStatus>
        }),
      ])
      setState(nextState); setAuth(nextAuth); setError(null)
    } catch { setError('Backend is offline. Start FastAPI on port 8000.') }
    finally { setIsLoading(false) }
  }, [request])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const connectTwitch = () => { window.location.href = `${apiBaseUrl}/api/auth/twitch/login` }

  const disconnectTwitch = async () => {
    setBusyAction('disconnect'); setError(null)
    try {
      const response = await fetch(`${apiBaseUrl}/api/auth/twitch/disconnect`, { method: 'POST' })
      if (!response.ok) throw new Error(`Request failed (${response.status})`)
      setAuth(await response.json() as AuthStatus)
    } catch { setError('Could not disconnect Twitch.') }
    finally { setBusyAction(null) }
  }

  const trackStream = async () => {
    setBusyAction('track'); setError(null)
    try {
      const response = await fetch(`${apiBaseUrl}/api/twitch/track`, { method: 'POST' })
      if (!response.ok) throw new Error(`Request failed (${response.status})`)
      setAuth(await response.json() as AuthStatus)
    } catch { setError('Could not start chat tracking. Confirm the channel is still live.') }
    finally { setBusyAction(null) }
  }

  const updateQuestion = async (questionId: string, action: QuestionStatus) => {
    setBusyAction(`${questionId}-${action}`); setError(null)
    try { setState(await request(`/api/questions/${questionId}/${action}`, { method: 'POST' })) }
    catch { setError('Could not update the question.') }
    finally { setBusyAction(null) }
  }

  const activeQuestions = state.questions.filter((q) => q.status === 'new' || q.status === 'pinned')
  const trackingInterrupted = Boolean(
    auth.stream && auth.tracking && ['reconnecting', 'disconnected', 'authentication_required'].includes(auth.status),
  )

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span /></div>
          <div><strong>ChatPulse</strong><span>Audience intelligence</span></div>
        </div>
        <div className="stream-status">
          <div className="channel-avatar">{auth.channel_name?.slice(0, 2).toUpperCase() ?? 'CP'}</div>
          <div><span className="eyebrow">TWITCH CHANNEL</span><strong>{auth.channel_name ?? 'Not connected'}</strong></div>
          <span className={`status-dot ${auth.status === 'ready' ? 'standby' : auth.status !== 'connected' ? 'offline' : ''}`} />
          <span className="connection-label">{auth.status.replace('_', ' ')}</span>
        </div>
      </header>

      <section className="control-strip" aria-label="Twitch connection controls">
        <div><span className="live-pulse" /><strong>{state.messages.length} messages</strong><span>in the current analysis window</span></div>
        <div className="scenario-buttons">
          <button className="ghost-button" disabled={!auth.configured || busyAction !== null} onClick={connectTwitch} type="button">
            {auth.channel_name ? 'Twitch connected' : auth.configured ? 'Connect Twitch' : 'Add Twitch credentials'}
          </button>
          <button className="primary-button connect-button" disabled={!auth.channel_name || auth.tracking || busyAction !== null} onClick={trackStream} type="button">
            {busyAction === 'track' ? 'Finding stream…' : auth.tracking ? 'Tracking stream' : 'Track streaming'}
          </button>
          {auth.channel_name && <button className="ghost-button" disabled={busyAction !== null} onClick={disconnectTwitch} type="button">Disconnect</button>}
        </div>
      </section>
      {auth.error && <div className="error-banner" role="alert">Twitch: {auth.error}</div>}
      {error && <div className="error-banner" role="alert">{error}</div>}

      {trackingInterrupted && (
        <div className="connection-modal-backdrop" role="alertdialog" aria-modal="true" aria-labelledby="connection-modal-title">
          <div className="connection-modal">
            <div className="connection-modal-icon">!</div>
            <span className="eyebrow">TWITCH CONNECTION LOST</span>
            <h2 id="connection-modal-title">Live chat tracking interrupted</h2>
            <p>ChatPulse lost its connection while your Twitch stream is still live. Automatic reconnection is in progress.</p>
            <div className="reconnect-progress"><span /><strong>Reconnecting…</strong></div>
          </div>
        </div>
      )}

      <main className="dashboard-grid">
        <section className="panel topic-panel">
          <PanelHeading eyebrow="LIVE ANALYSIS" title="Topic radar" subtitle="What your audience is talking about" icon="⌁" />
          <div className="panel-content topic-list">
            {isLoading ? <EmptyState title="Connecting…" copy="Reading the latest audience state." />
              : state.topics.length === 0 ? <EmptyState title="Waiting for chat" copy="Connect Twitch, then send a message in the channel." />
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
              : activeQuestions.length === 0 ? <EmptyState title="No questions detected" copy="Questions from real Twitch chat will appear here." />
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
          <PanelHeading eyebrow="TWITCH" title="Live stream" subtitle="Your current Twitch broadcast" icon="▶" />
          <div className="panel-content live-player-content">
            {auth.stream && auth.channel_login ? (
              <iframe
                allow="autoplay; fullscreen"
                allowFullScreen
                className="twitch-player"
                src={`https://player.twitch.tv/?channel=${encodeURIComponent(auth.channel_login)}&parent=${encodeURIComponent(window.location.hostname)}&autoplay=false&muted=true`}
                title={`${auth.channel_name ?? auth.channel_login} live stream`}
              />
            ) : (
              <div className="live-player-empty"><div>▶</div><strong>No live stream</strong><span>Connect Twitch and start broadcasting to see the video here.</span></div>
            )}
            {auth.stream && <div className="live-player-meta"><span className="live-badge">LIVE</span><div><strong>{auth.stream.title}</strong><span>{auth.stream.game_name} · {auth.stream.viewer_count} viewers</span></div></div>}
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

