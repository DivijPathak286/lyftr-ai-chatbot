import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const newSession = () => `s-${crypto.randomUUID().slice(0, 8)}`

function App() {
  const [sessionId, setSessionId] = useState(() => newSession())
  const [sessions, setSessions] = useState([])
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [apiStatus, setApiStatus] = useState('Checking connection')
  const [failure, setFailure] = useState('none')
  const [historyLoading, setHistoryLoading] = useState(false)
  const bottomRef = useRef(null)

  
useEffect(() => {
  let cancelled = false

  async function checkHealth() {
    try {
      const response = await fetch(`${API}/health`)
      if (!response.ok) throw new Error('Backend unavailable')

      const data = await response.json()

      if (!cancelled) {
        setApiStatus(data.status === 'ok' ? 'Connected' : 'Unavailable')
      }
    } catch {
      if (!cancelled) {
        setApiStatus('Backend unavailable')
      }
    }
  }

  checkHealth()

  return () => {
    cancelled = true
  }
}, [])

useEffect(() => {
  let cancelled = false

  async function loadMessages() {
    setMessages([])

    try {
      const response = await fetch(
        `${API}/sessions/${sessionId}/messages`
      )

      if (response.status === 404) {
        return
      }

      if (!response.ok) {
        throw new Error('Could not load previous messages')
      }

      const data = await response.json()

      if (!cancelled) {
        setMessages(data.messages || [])
      }
    } catch (err) {
      if (!cancelled) {
        console.error('Chat history loading error:', err)
      }
    }
  }

  loadMessages()

  return () => {
    cancelled = true
  }
}, [sessionId])

useEffect(() => {
  let cancelled = false

  async function loadSessions() {
    setHistoryLoading(true)

    try {
      const response = await fetch(`${API}/sessions`)

      if (!response.ok) {
        throw new Error('Could not load conversations')
      }

      const data = await response.json()

      if (!cancelled) {
        setSessions(data.sessions || [])
      }
    } catch (err) {
      console.error('Conversation list loading error:', err)
    } finally {
      if (!cancelled) {
        setHistoryLoading(false)
      }
    }
  }

  loadSessions()

  return () => {
    cancelled = true
  }
}, [sessionId, messages.length])

useEffect(() => {
  bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
}, [messages, loading])


  async function sendMessage(e) {
    e?.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setError('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const headers = { 'Content-Type': 'application/json' }
      if (failure !== 'none') headers['X-Simulate-Failure'] = failure
      const body = { session_id: sessionId, message: text }
      if (systemPrompt.trim()) body.system_prompt = systemPrompt.trim()
      const response = await fetch(`${API}/chat`, { method: 'POST', headers, body: JSON.stringify(body) })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`)
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply, metadata: data.metadata }])
    } catch (err) {
      const msg = err.message || 'Unable to reach the assistant. Please try again.'
      setError(msg)
    } finally { setLoading(false) }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">L</div><div><b>Lyftr<span>AI</span></b><small>INTELLIGENCE, IN MOTION</small></div></div>
      <button
  className="new-chat"
  onClick={() => {
    const id = newSession()

    localStorage.setItem('lyftr_session_id', id)
    setSessionId(id)
    setMessages([])
    setSystemPrompt('')
    setError('')
    setInput('')
  }}
>
  <span>＋</span> New conversation
</button>
<div className="history-section">
  <div className="side-label">RECENT CONVERSATIONS</div>

  {historyLoading && (
    <div className="history-empty">Loading conversations...</div>
  )}

  {!historyLoading && sessions.length === 0 && (
    <div className="history-empty">No previous conversations</div>
  )}

  {sessions.map((session) => (
    <button
      key={session.session_id}
      className={`history-item ${
        session.session_id === sessionId ? 'active' : ''
      }`}
      onClick={() => {
        localStorage.setItem('lyftr_session_id', session.session_id)
        setSessionId(session.session_id)
        setMessages([])
        setError('')
        setInput('')
      }}
    >
      <span className="history-title">
        {session.last_message || 'New conversation'}
      </span>
      <span className="history-count">
        {session.message_count} messages
      </span>
    </button>
  ))}
</div>
      <div className="side-label">WORKSPACE</div>
      <div className="side-item active"><span>◈</span> AI Assistant</div>
      <div className="side-bottom"><div className="status-dot"/><div><b>{apiStatus}</b><small>API connection</small></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><span className="eyebrow">WORKSPACE / CHAT</span><h1>AI Assistant</h1></div><button className="settings-btn" onClick={() => setShowSettings(v => !v)}>⚙ <span>Settings</span></button></header>
      {showSettings && <section className="settings-panel"><label htmlFor="system-prompt-input">Session system prompt</label><textarea id="system-prompt-input" data-testid="system-prompt-input" value={systemPrompt} onChange={e => setSystemPrompt(e.target.value)} placeholder="Optional: define how the assistant should respond…"/><div className="setting-note">Applied to this session's requests.</div><label htmlFor="failure-mode">Failover demonstration</label><select id="failure-mode" value={failure} onChange={e => setFailure(e.target.value)}><option value="none">Normal request</option><option value="key_1=429">Simulate key_1 rate limit (429)</option><option value="key_1=500">Simulate key_1 server error (500)</option><option value="*=429">Simulate all keys rate-limited (503)</option></select><div className="setting-note">Requires ENABLE_FAILURE_SIMULATION=true on the backend.</div></section>}
      <section className="chat-area">
        {messages.length === 0 ? <div className="welcome"><div className="orb">✳</div><div className="eyebrow">YOUR AI WORKSPACE</div><h2>How can I help<br/><em>you today?</em></h2><p>Ask a question, explore an idea, or get something done.</p><div className="suggestions"><button onClick={() => setInput('Explain how API key failover works.')}>↗ <span>Explain key failover</span></button><button onClick={() => setInput('What are the benefits of response caching?')}>◷ <span>Explore response caching</span></button></div></div> :
          <div className="conversation">{messages.map((m, i) => <div key={i} className={`message-row ${m.role}`}><div className={`avatar ${m.role}`}>{m.role === 'assistant' ? '✳' : 'Y'}</div><div className="message-content"><div className="speaker">{m.role === 'assistant' ? 'LYFTR AI' : 'YOU'}</div>{m.role === 'assistant' ? <div className="assistant-card" data-testid="assistant-message"><div className="reply-text">{m.content}</div><div className="metadata"><span className={`source ${m.metadata?.resolution_source === 'LLM_CACHE' ? 'cached' : ''}`} data-testid="meta-source">{m.metadata?.resolution_source}</span><span data-testid="meta-model"><b>Model</b> {m.metadata?.model}</span><span data-testid="meta-latency"><b>Latency</b> {m.metadata?.latency_ms} ms</span><span data-testid="meta-input-tokens"><b>In</b> {m.metadata?.input_tokens}</span><span data-testid="meta-output-tokens"><b>Out</b> {m.metadata?.output_tokens}</span></div></div> : <div className="user-bubble">{m.content}</div>}</div></div>)}
            {loading && <div className="message-row assistant"><div className="avatar assistant">✳</div><div className="message-content"><div className="speaker">LYFTR AI</div><div className="typing"><i/><i/><i/> <span>Thinking…</span></div></div></div>}
            {error && <div className="error-message">⚠ {error}</div>}<div ref={bottomRef}/></div>}
      </section>
      <form className="composer" onSubmit={sendMessage}><div className="input-wrap"><textarea data-testid="chat-input" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) sendMessage(e) }} placeholder="Message Lyftr AI…" rows="1"/><button data-testid="send-button" type="submit" disabled={!input.trim() || loading} aria-label="Send message">↑</button></div><div className="composer-foot"><span>↵ Enter to send · Shift + Enter for new line</span><span>Powered by LiteLLM</span></div></form>
    </main>
  </div>
}
createRoot(document.getElementById('root')).render(<App />)