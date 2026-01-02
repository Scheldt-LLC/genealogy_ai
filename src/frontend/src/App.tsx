import { useState, useEffect } from 'react'
import './App.css'
import Upload from './components/Upload'
import Chat from './components/Chat'
import Tree from './components/Tree'

interface HealthResponse {
  status: string
  service: string
  version: string
}

interface ConfigResponse {
  azure_configured: boolean
  openai_configured: boolean
  tesseract_available: boolean
}

type Tab = 'upload' | 'chat' | 'tree'
type Theme = 'light' | 'dark' | 'system'

function App() {
  const [apiStatus, setApiStatus] = useState<HealthResponse | null>(null)
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('upload')
  const [openaiKey, setOpenaiKey] = useState<string>('')
  const [showKeyInput, setShowKeyInput] = useState(false)
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('theme') as Theme | null
    return saved || 'system'
  })

  useEffect(() => {
    // Test API connection
    fetch('/api/health')
      .then((res) => res.json())
      .then((data: HealthResponse) => setApiStatus(data))
      .catch((err) => setError(err.message))

    // Fetch config
    fetch('/api/config')
      .then((res) => res.json())
      .then((data: ConfigResponse) => setConfig(data))
      .catch((err) => console.error('Failed to fetch config:', err))

    // Load session key
    const savedKey = sessionStorage.getItem('openai_api_key')
    if (savedKey) setOpenaiKey(savedKey)
  }, [])

  // Apply theme
  useEffect(() => {
    const root = document.documentElement

    if (theme === 'system') {
      root.removeAttribute('data-theme')
    } else {
      root.setAttribute('data-theme', theme)
    }

    localStorage.setItem('theme', theme)
  }, [theme])

  const cycleTheme = () => {
    setTheme((current) => {
      if (current === 'system') return 'light'
      if (current === 'light') return 'dark'
      return 'system'
    })
  }

  const handleSaveKey = () => {
    sessionStorage.setItem('openai_api_key', openaiKey)
    setShowKeyInput(false)
    // We don't need to reload config because this is session-only
    // but we might want to show a "Key Set" status
  }

  const isOpenAIReady = config?.openai_configured || !!openaiKey

  return (
    <>
      <header className="app-header">
        <div className="header-main">
          <h1>Genealogy AI</h1>
          <div className="status-group">
            <div className="status">
              {apiStatus ? (
                <span className="status-ok">
                  ✓ Connected to {apiStatus.service}
                </span>
              ) : error ? (
                <span className="status-error">✗ {error}</span>
              ) : (
                <span>Connecting...</span>
              )}
            </div>

            <div className="status openai-status">
              {isOpenAIReady ? (
                <span className="status-ok">✓ OpenAI Ready</span>
              ) : (
                <span className="status-warning" onClick={() => setShowKeyInput(!showKeyInput)}>
                  ⚠ OpenAI Key Missing (Click to fix)
                </span>
              )}
            </div>

            <button className="theme-toggle" onClick={cycleTheme} title={`Theme: ${theme}`}>
              {theme === 'light' && '☀️'}
              {theme === 'dark' && '🌙'}
              {theme === 'system' && '💻'}
            </button>
          </div>
        </div>

        {showKeyInput && !config?.openai_configured && (
          <div className="key-input-overlay">
            <div className="key-input-container">
              <h3>OpenAI Configuration</h3>
              <p>Add <code>OPENAI_API_KEY</code> to your <code>.env</code> file for permanent access, or enter it here for this session only.</p>
              <input
                type="password"
                placeholder="sk-..."
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
              />
              <div className="key-input-actions">
                <button onClick={handleSaveKey}>Save for Session</button>
                <button className="secondary" onClick={() => setShowKeyInput(false)}>Close</button>
              </div>
            </div>
          </div>
        )}
      </header>

      <nav className="app-nav">
        <button
          className={`nav-tab ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          Upload Documents
        </button>
        <button
          className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          Chat
        </button>
        <button
          className={`nav-tab ${activeTab === 'tree' ? 'active' : ''}`}
          onClick={() => setActiveTab('tree')}
        >
          Family Tree
        </button>
      </nav>

      <main>
        {activeTab === 'upload' && <Upload />}
        {activeTab === 'chat' && <Chat />}
        {activeTab === 'tree' && <Tree />}
      </main>
    </>
  )
}

export default App
