import { useState, useRef, useEffect } from 'react'
import './Chat.css'

interface Source {
  source: string
  page: number
  document_id: number | null
  text_preview: string
}

interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  sources?: Source[]
  timestamp: Date
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!input.trim() || loading) return

    const question = input.trim()
    setInput('')
    setError(null)

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: question,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setLoading(true)

    try {
      const sessionOpenAIKey = sessionStorage.getItem('openai_api_key')
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          question,
          openai_key: sessionOpenAIKey 
        }),
      })

      const data = await response.json()

      if (response.ok && data.success) {
        // Add assistant message
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: data.answer,
          sources: data.sources,
          timestamp: new Date(),
        }

        setMessages((prev) => [...prev, assistantMessage])
      } else {
        setError(data.error || 'Failed to get response')
      }
    } catch (err) {
      setError('Failed to send message: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-container">
      <h2>Ask About Your Documents</h2>
      <p className="chat-description">
        Ask questions about your genealogy documents and get AI-powered answers.
      </p>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <p>Start a conversation by asking a question about your documents.</p>
            <p className="chat-hint">
              For example: "Who are the parents of John Byrne?" or "What events
              happened in 1850?"
            </p>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.type}`}>
                <div className="message-content">
                  <div className="message-text">{message.content}</div>
                  {message.sources && message.sources.length > 0 && (
                    <div className="message-sources">
                      <strong>Sources:</strong>
                      {message.sources.map((source, idx) => (
                        <div key={idx} className="source-item">
                          {source.document_id ? (
                            <a
                              href={`/api/documents/${source.document_id}/file`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="source-file source-link"
                              title="View original document"
                            >
                              {source.source.split('/').pop()} (Page {source.page}) 👁️
                            </a>
                          ) : (
                            <span className="source-file">
                              {source.source.split('/').pop()} (Page {source.page})
                            </span>
                          )}
                          <div className="source-preview">{source.text_preview}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="message-time">
                  {message.timestamp.toLocaleTimeString()}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </>
        )}

        {loading && (
          <div className="message assistant loading">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="chat-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      <form className="chat-input-form" onSubmit={sendMessage}>
        <input
          type="text"
          className="chat-input"
          placeholder="Ask a question about your documents..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="chat-submit" disabled={loading || !input.trim()}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </form>
    </div>
  )
}
