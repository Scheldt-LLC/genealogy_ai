import { useState, useEffect } from 'react'
import DocumentLinks from './DocumentLinks'
import './PersonDocuments.css'

interface Person {
  id: number
  primary_name: string
  birth_year: number | null
  death_year: number | null
}

interface PersonListResponse {
  success: boolean
  people: Person[]
}

interface Document {
  id: number
  source: string
  document_type: string | null
}

interface DocumentListResponse {
  success: boolean
  documents: Document[]
}

export default function PersonDocuments() {
  const [people, setPeople] = useState<Person[]>([])
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null)
  const [showAddLink, setShowAddLink] = useState(false)
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocument, setSelectedDocument] = useState<string>('')
  const [linkType, setLinkType] = useState<string>('mentioned_in')
  const [notes, setNotes] = useState<string>('')
  const [adding, setAdding] = useState(false)
  const [addSuccess, setAddSuccess] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  useEffect(() => {
    fetchPeople()
    fetchDocuments()
  }, [])

  const fetchPeople = async () => {
    try {
      const response = await fetch('/api/people')
      const data: PersonListResponse = await response.json()
      if (data.success) {
        setPeople(data.people)
      }
    } catch (err) {
      console.error('Failed to fetch people:', err)
    }
  }

  const fetchDocuments = async () => {
    try {
      const response = await fetch('/api/documents')
      const data: DocumentListResponse = await response.json()
      if (data.success) {
        setDocuments(data.documents)
      }
    } catch (err) {
      console.error('Failed to fetch documents:', err)
    }
  }

  const handleAddLink = async () => {
    if (!selectedPerson || !selectedDocument) {
      return
    }

    try {
      setAdding(true)
      setAddError(null)
      setAddSuccess(false)

      const response = await fetch(`/api/people/${selectedPerson.id}/documents`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          document_id: parseInt(selectedDocument),
          link_type: linkType,
          notes: notes || null,
        }),
      })

      const data = await response.json()

      if (response.ok && data.success) {
        setAddSuccess(true)
        setSelectedDocument('')
        setNotes('')
        setShowAddLink(false)
        // Trigger refresh by re-selecting person
        const current = selectedPerson
        setSelectedPerson(null)
        setTimeout(() => setSelectedPerson(current), 10)
        setTimeout(() => setAddSuccess(false), 3000)
      } else {
        setAddError(data.error || 'Failed to add link')
      }
    } catch (err) {
      setAddError('Failed to add link: ' + (err as Error).message)
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="person-documents-container">
      <div className="person-documents-sidebar">
        <div className="sidebar-header">
          <h3>Select Person</h3>
        </div>
        <div className="people-list">
          {people.map((person) => (
            <div
              key={person.id}
              className={`person-item ${selectedPerson?.id === person.id ? 'active' : ''}`}
              onClick={() => setSelectedPerson(person)}
            >
              <div className="person-name">{person.primary_name}</div>
              <div className="person-dates">
                {person.birth_year && `b. ${person.birth_year}`}
                {person.death_year && ` - d. ${person.death_year}`}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="person-documents-main">
        {!selectedPerson ? (
          <div className="no-selection">
            <p>Select a person to view their linked documents</p>
          </div>
        ) : (
          <>
            <div className="main-header">
              <h2>{selectedPerson.primary_name}</h2>
              <button
                className="add-link-button"
                onClick={() => setShowAddLink(!showAddLink)}
              >
                {showAddLink ? 'Cancel' : '+ Add Document Link'}
              </button>
            </div>

            {addSuccess && (
              <div className="add-success">
                Document link added successfully!
              </div>
            )}

            {showAddLink && (
              <div className="add-link-panel">
                <h4>Add Document Link</h4>
                {addError && (
                  <div className="add-error">
                    <strong>Error:</strong> {addError}
                  </div>
                )}
                <div className="add-link-form">
                  <div className="form-group">
                    <label>Document:</label>
                    <select
                      value={selectedDocument}
                      onChange={(e) => setSelectedDocument(e.target.value)}
                    >
                      <option value="">Select a document...</option>
                      {documents.map((doc) => (
                        <option key={doc.id} value={doc.id}>
                          {doc.source}
                          {doc.document_type && ` (${doc.document_type})`}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Link Type:</label>
                    <select value={linkType} onChange={(e) => setLinkType(e.target.value)}>
                      <option value="mentioned_in">Mentioned In</option>
                      <option value="portrait_of">Portrait Of</option>
                      <option value="signed_by">Signed By</option>
                      <option value="witness">Witness</option>
                      <option value="about">About</option>
                      <option value="extracted_from">Extracted From</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Notes (optional):</label>
                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="Add any notes about this link..."
                      rows={3}
                    />
                  </div>

                  <button
                    className="submit-link-button"
                    onClick={handleAddLink}
                    disabled={!selectedDocument || adding}
                  >
                    {adding ? 'Adding...' : 'Add Link'}
                  </button>
                </div>
              </div>
            )}

            <div className="document-links-wrapper">
              <DocumentLinks
                personId={selectedPerson.id}
                personName={selectedPerson.primary_name}
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
