import { useState, useEffect } from 'react'
import './EntityReview.css'

interface PendingEntity {
  id: number
  primary_name: string
  name_variants: string[]
  family_name: string | null
  family_side: string | null
  notes: string | null
  events: Array<{
    event_type: string
    date: string | null
    place: string | null
    description: string | null
  }>
}

interface ExistingEntity {
  id: number
  primary_name: string
  family_name: string | null
  family_side: string | null
  events: Array<{
    event_type: string
    date: string | null
    place: string | null
    description: string | null
  }>
}

interface EntityMatch {
  match_id: number
  batch_id: string
  match_type: string
  confidence: number
  reasons: string[]
  pending_entity: PendingEntity
  existing_entity: ExistingEntity | null
}

interface PendingResponse {
  success: boolean
  pending_count: number
  matches: EntityMatch[]
}

export default function EntityReview() {
  const [matches, setMatches] = useState<EntityMatch[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [processing, setProcessing] = useState<number | null>(null)

  useEffect(() => {
    fetchPendingMatches()
  }, [])

  const fetchPendingMatches = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch('/api/entities/pending')
      const data: PendingResponse = await response.json()

      if (data.success) {
        setMatches(data.matches)
      } else {
        setError('Failed to load pending matches')
      }
    } catch (err) {
      setError('Error loading pending matches: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (matchId: number) => {
    try {
      setProcessing(matchId)
      setError(null)

      const response = await fetch(`/api/entities/approve/${matchId}`, {
        method: 'POST',
      })

      const data = await response.json()

      if (response.ok && data.success) {
        // Remove from list
        setMatches((prev) => prev.filter((m) => m.match_id !== matchId))
      } else {
        setError(data.error || 'Failed to approve match')
      }
    } catch (err) {
      setError('Error approving match: ' + (err as Error).message)
    } finally {
      setProcessing(null)
    }
  }

  const handleReject = async (matchId: number) => {
    try {
      setProcessing(matchId)
      setError(null)

      const response = await fetch(`/api/entities/reject/${matchId}`, {
        method: 'POST',
      })

      const data = await response.json()

      if (response.ok && data.success) {
        // Remove from list
        setMatches((prev) => prev.filter((m) => m.match_id !== matchId))
      } else {
        setError(data.error || 'Failed to reject match')
      }
    } catch (err) {
      setError('Error rejecting match: ' + (err as Error).message)
    } finally {
      setProcessing(null)
    }
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'high'
    if (confidence >= 0.75) return 'medium'
    return 'low'
  }

  if (loading) {
    return (
      <div className="entity-review-container">
        <div className="loading-state">Loading pending matches...</div>
      </div>
    )
  }

  return (
    <div className="entity-review-container">
      <div className="review-header">
        <h2>Entity Review</h2>
        <p className="subtitle">
          Review and approve uncertain entity matches (confidence &lt; 95%)
        </p>
      </div>

      {error && (
        <div className="review-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {matches.length === 0 ? (
        <div className="empty-state">
          <p>✨ No pending matches to review!</p>
          <p className="subtitle">All entities have been processed.</p>
        </div>
      ) : (
        <div className="matches-list">
          <div className="matches-header">
            <span>{matches.length} pending match{matches.length !== 1 ? 'es' : ''}</span>
          </div>

          {matches.map((match) => (
            <div key={match.match_id} className="match-card">
              <div className="match-header">
                <div className="match-info">
                  <span className={`confidence-badge ${getConfidenceColor(match.confidence)}`}>
                    {(match.confidence * 100).toFixed(0)}% confidence
                  </span>
                  <span className="match-type">{match.match_type.replace('_', ' → ')}</span>
                </div>
                <div className="match-actions">
                  <button
                    className="approve-button"
                    onClick={() => handleApprove(match.match_id)}
                    disabled={processing === match.match_id}
                  >
                    {processing === match.match_id ? 'Approving...' : '✓ Merge'}
                  </button>
                  <button
                    className="reject-button"
                    onClick={() => handleReject(match.match_id)}
                    disabled={processing === match.match_id}
                  >
                    {processing === match.match_id ? 'Rejecting...' : '✗ Keep Separate'}
                  </button>
                </div>
              </div>

              <div className="match-reasons">
                <strong>Match reasons:</strong> {match.reasons.join(', ')}
              </div>

              <div className="match-comparison">
                {/* Pending Entity */}
                <div className="entity-panel pending">
                  <h4>Extracted Entity</h4>
                  <div className="entity-details">
                    <div className="entity-name">{match.pending_entity.primary_name}</div>

                    {match.pending_entity.name_variants.length > 0 && (
                      <div className="name-variants">
                        <strong>Variants:</strong> {match.pending_entity.name_variants.join(', ')}
                      </div>
                    )}

                    {match.pending_entity.family_name && (
                      <div className="family-info">
                        <span className="family-badge">{match.pending_entity.family_name}</span>
                        {match.pending_entity.family_side && (
                          <span className="side-badge">{match.pending_entity.family_side}</span>
                        )}
                      </div>
                    )}

                    {match.pending_entity.events.length > 0 && (
                      <div className="events-list">
                        <strong>Events:</strong>
                        <ul>
                          {match.pending_entity.events.map((event, idx) => (
                            <li key={idx}>
                              <span className="event-type">{event.event_type}</span>
                              {event.date && <span className="event-date">: {event.date}</span>}
                              {event.place && (
                                <span className="event-place"> in {event.place}</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {match.pending_entity.notes && (
                      <div className="notes">
                        <strong>Notes:</strong> {match.pending_entity.notes}
                      </div>
                    )}
                  </div>
                </div>

                {/* Existing Entity */}
                {match.existing_entity && (
                  <div className="entity-panel existing">
                    <h4>Existing Person (ID: {match.existing_entity.id})</h4>
                    <div className="entity-details">
                      <div className="entity-name">{match.existing_entity.primary_name}</div>

                      {match.existing_entity.family_name && (
                        <div className="family-info">
                          <span className="family-badge">{match.existing_entity.family_name}</span>
                          {match.existing_entity.family_side && (
                            <span className="side-badge">{match.existing_entity.family_side}</span>
                          )}
                        </div>
                      )}

                      {match.existing_entity.events.length > 0 && (
                        <div className="events-list">
                          <strong>Events:</strong>
                          <ul>
                            {match.existing_entity.events.map((event, idx) => (
                              <li key={idx}>
                                <span className="event-type">{event.event_type}</span>
                                {event.date && <span className="event-date">: {event.date}</span>}
                                {event.place && (
                                  <span className="event-place"> in {event.place}</span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
