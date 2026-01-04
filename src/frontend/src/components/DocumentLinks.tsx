import { useEffect, useState } from 'react'
import './DocumentLinks.css'

interface DocumentLink {
  document_id: number
  link_type: string
  notes: string | null
  source: string
  page: number | null
  document_type: string | null
  created_at: string
}

interface DocumentLinksResponse {
  success: boolean
  person_id: number
  documents: DocumentLink[]
  count: number
}

interface DocumentLinksProps {
  personId: number
  personName?: string
  onClose?: () => void
}

export default function DocumentLinks({ personId, personName, onClose }: DocumentLinksProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [documents, setDocuments] = useState<DocumentLink[]>([])
  const [unlinking, setUnlinking] = useState<number | null>(null)

  useEffect(() => {
    fetchDocuments()
  }, [personId])

  const fetchDocuments = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`/api/people/${personId}/documents`)
      const data: DocumentLinksResponse = await response.json()

      if (response.ok && data.success) {
        setDocuments(data.documents)
      } else {
        setError('Failed to load documents')
      }
    } catch (err) {
      setError('Failed to load documents: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleUnlink = async (documentId: number) => {
    if (!confirm('Are you sure you want to unlink this document?')) {
      return
    }

    try {
      setUnlinking(documentId)
      const response = await fetch(`/api/people/${personId}/documents/${documentId}`, {
        method: 'DELETE',
      })

      const data = await response.json()

      if (response.ok && data.success) {
        // Remove from local state
        setDocuments((prev) => prev.filter((doc) => doc.document_id !== documentId))
      } else {
        setError(data.error || 'Failed to unlink document')
      }
    } catch (err) {
      setError('Failed to unlink document: ' + (err as Error).message)
    } finally {
      setUnlinking(null)
    }
  }

  const handleViewDocument = (documentId: number) => {
    window.open(`/api/documents/${documentId}/file`, '_blank')
  }

  const getLinkTypeLabel = (linkType: string): string => {
    const labels: Record<string, string> = {
      extracted_from: 'Extracted From',
      mentioned_in: 'Mentioned In',
      portrait_of: 'Portrait Of',
      signed_by: 'Signed By',
      witness: 'Witness',
      about: 'About',
    }
    return labels[linkType] || linkType.replace(/_/g, ' ')
  }

  const getLinkTypeClass = (linkType: string): string => {
    const classes: Record<string, string> = {
      extracted_from: 'link-extracted',
      mentioned_in: 'link-mentioned',
      portrait_of: 'link-portrait',
      signed_by: 'link-signed',
      witness: 'link-witness',
      about: 'link-about',
    }
    return classes[linkType] || 'link-default'
  }

  return (
    <div className="document-links-container">
      <div className="document-links-header">
        <h3>
          Linked Documents
          {personName && <span className="person-name-subtitle"> for {personName}</span>}
        </h3>
        {onClose && (
          <button className="close-button" onClick={onClose} title="Close">
            ✕
          </button>
        )}
      </div>

      {loading ? (
        <div className="document-links-loading">
          <p>Loading documents...</p>
        </div>
      ) : error ? (
        <div className="document-links-error">
          <strong>Error:</strong> {error}
        </div>
      ) : documents.length === 0 ? (
        <div className="document-links-empty">
          <p>No documents linked to this person.</p>
        </div>
      ) : (
        <div className="document-links-list">
          {documents.map((doc) => (
            <div key={doc.document_id} className="document-link-item">
              <div className="document-link-info">
                <div className="document-link-header">
                  <span className="document-source">{doc.source}</span>
                  {doc.page && <span className="document-page">Page {doc.page}</span>}
                </div>

                <div className="document-link-badges">
                  <span className={`link-type-badge ${getLinkTypeClass(doc.link_type)}`}>
                    {getLinkTypeLabel(doc.link_type)}
                  </span>
                  {doc.document_type && (
                    <span className="document-type-badge">
                      {doc.document_type.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>

                {doc.notes && (
                  <div className="document-link-notes">
                    <strong>Notes:</strong> {doc.notes}
                  </div>
                )}

                <div className="document-link-meta">
                  <span className="document-created">
                    Linked {new Date(doc.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>

              <div className="document-link-actions">
                <button
                  className="view-button"
                  onClick={() => handleViewDocument(doc.document_id)}
                  title="View document"
                >
                  View
                </button>
                <button
                  className="unlink-button"
                  onClick={() => handleUnlink(doc.document_id)}
                  disabled={unlinking === doc.document_id}
                  title="Unlink document"
                >
                  {unlinking === doc.document_id ? 'Unlinking...' : 'Unlink'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
