import { useState, useEffect } from 'react'
import './FamilyManager.css'

interface Person {
  id: number
  primary_name: string
  birth_year: number | null
  death_year: number | null
  family_name: string | null
  family_side: string | null
}

interface PersonListResponse {
  success: boolean
  people: Person[]
}

interface Family {
  family_name: string
  person_count: number
  paternal_count: number
  maternal_count: number
  unspecified_count: number
}

interface FamilyListResponse {
  success: boolean
  families: Family[]
}

interface ReconciliationResult {
  success: boolean
  candidates_found: number
  candidates_above_threshold: number
  duplicates_merged: number
  skipped: number
  errors: string[]
  min_confidence: number
}

export default function FamilyManager() {
  const [people, setPeople] = useState<Person[]>([])
  const [families, setFamilies] = useState<Family[]>([])
  const [selectedPeople, setSelectedPeople] = useState<Set<number>>(new Set())
  const [targetFamily, setTargetFamily] = useState<string>('')
  const [newFamilyName, setNewFamilyName] = useState<string>('')
  const [familySide, setFamilySide] = useState<string>('')
  const [filterFamily, setFilterFamily] = useState<string>('all')
  const [assigning, setAssigning] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reconciliation state
  const [reconciling, setReconciling] = useState(false)
  const [reconcileResult, setReconcileResult] = useState<ReconciliationResult | null>(null)
  const [reconcileError, setReconcileError] = useState<string | null>(null)

  useEffect(() => {
    fetchPeople()
    fetchFamilies()
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

  const fetchFamilies = async () => {
    try {
      const response = await fetch('/api/families')
      const data: FamilyListResponse = await response.json()
      if (data.success) {
        setFamilies(data.families)
      }
    } catch (err) {
      console.error('Failed to fetch families:', err)
    }
  }

  const handleSelectAll = () => {
    const filtered = getFilteredPeople()
    if (selectedPeople.size === filtered.length) {
      setSelectedPeople(new Set())
    } else {
      setSelectedPeople(new Set(filtered.map((p) => p.id)))
    }
  }

  const handleTogglePerson = (personId: number) => {
    const newSelected = new Set(selectedPeople)
    if (newSelected.has(personId)) {
      newSelected.delete(personId)
    } else {
      newSelected.add(personId)
    }
    setSelectedPeople(newSelected)
  }

  const handleAssignFamily = async () => {
    if (selectedPeople.size === 0) {
      setError('Please select at least one person')
      return
    }

    const familyToAssign = targetFamily === 'new' ? newFamilyName : targetFamily
    if (!familyToAssign) {
      setError('Please select or enter a family name')
      return
    }

    try {
      setAssigning(true)
      setError(null)
      setSuccess(false)

      // Assign each selected person to the family
      const promises = Array.from(selectedPeople).map((personId) =>
        fetch(`/api/people/${personId}/family`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            family_name: familyToAssign,
            family_side: familySide || null,
          }),
        })
      )

      const results = await Promise.all(promises)
      const allSucceeded = results.every((r) => r.ok)

      if (allSucceeded) {
        setSuccess(true)
        setSelectedPeople(new Set())
        setTargetFamily('')
        setNewFamilyName('')
        setFamilySide('')
        // Refresh data
        fetchPeople()
        fetchFamilies()
        setTimeout(() => setSuccess(false), 3000)
      } else {
        setError('Some assignments failed. Please try again.')
      }
    } catch (err) {
      setError('Failed to assign families: ' + (err as Error).message)
    } finally {
      setAssigning(false)
    }
  }

  const handleReconcile = async () => {
    try {
      setReconciling(true)
      setReconcileError(null)
      setReconcileResult(null)

      const response = await fetch('/api/reconcile', {
        method: 'POST',
      })

      const data: ReconciliationResult = await response.json()

      if (response.ok && data.success) {
        setReconcileResult(data)
        // Refresh people list if any were merged
        if (data.duplicates_merged > 0) {
          fetchPeople()
          fetchFamilies()
        }
      } else {
        setReconcileError('Reconciliation failed')
      }
    } catch (err) {
      setReconcileError('Failed to run reconciliation: ' + (err as Error).message)
    } finally {
      setReconciling(false)
    }
  }

  const getFilteredPeople = () => {
    if (filterFamily === 'all') return people
    if (filterFamily === 'unassigned') return people.filter((p) => !p.family_name)
    return people.filter((p) => p.family_name === filterFamily)
  }

  const filteredPeople = getFilteredPeople()
  const allSelected = filteredPeople.length > 0 && selectedPeople.size === filteredPeople.length

  return (
    <div className="family-manager-container">
      <div className="family-manager-header">
        <h2>Family Manager</h2>
        <p className="subtitle">Bulk assign people to families</p>
      </div>

      {success && (
        <div className="manager-success">
          Successfully assigned {selectedPeople.size} people to family!
        </div>
      )}

      {error && (
        <div className="manager-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="manager-controls">
        <div className="control-section">
          <h3>Filter People</h3>
          <div className="filter-group">
            <label>Show:</label>
            <select value={filterFamily} onChange={(e) => setFilterFamily(e.target.value)}>
              <option value="all">All People ({people.length})</option>
              <option value="unassigned">
                Unassigned ({people.filter((p) => !p.family_name).length})
              </option>
              {families.map((family) => (
                <option key={family.family_name} value={family.family_name}>
                  {family.family_name} ({family.person_count})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="control-section">
          <h3>Assign Selected to Family</h3>
          <div className="assign-form">
            <div className="form-row">
              <label>Family:</label>
              <select
                value={targetFamily}
                onChange={(e) => setTargetFamily(e.target.value)}
                disabled={selectedPeople.size === 0}
              >
                <option value="">Select family...</option>
                {families.map((family) => (
                  <option key={family.family_name} value={family.family_name}>
                    {family.family_name}
                  </option>
                ))}
                <option value="new">+ Create New Family</option>
              </select>

              {targetFamily === 'new' && (
                <input
                  type="text"
                  placeholder="Enter new family name..."
                  value={newFamilyName}
                  onChange={(e) => setNewFamilyName(e.target.value)}
                />
              )}
            </div>

            <div className="form-row">
              <label>Family Side (optional):</label>
              <div className="radio-group">
                <label>
                  <input
                    type="radio"
                    name="family-side"
                    value=""
                    checked={familySide === ''}
                    onChange={(e) => setFamilySide(e.target.value)}
                    disabled={selectedPeople.size === 0}
                  />
                  Not specified
                </label>
                <label>
                  <input
                    type="radio"
                    name="family-side"
                    value="paternal"
                    checked={familySide === 'paternal'}
                    onChange={(e) => setFamilySide(e.target.value)}
                    disabled={selectedPeople.size === 0}
                  />
                  Paternal
                </label>
                <label>
                  <input
                    type="radio"
                    name="family-side"
                    value="maternal"
                    checked={familySide === 'maternal'}
                    onChange={(e) => setFamilySide(e.target.value)}
                    disabled={selectedPeople.size === 0}
                  />
                  Maternal
                </label>
              </div>
            </div>

            <button
              className="assign-button"
              onClick={handleAssignFamily}
              disabled={selectedPeople.size === 0 || assigning}
            >
              {assigning
                ? 'Assigning...'
                : `Assign ${selectedPeople.size} ${selectedPeople.size === 1 ? 'Person' : 'People'}`}
            </button>
          </div>
        </div>
      </div>

      <div className="reconciliation-section">
        <div className="reconciliation-header">
          <div>
            <h3>Find & Merge Duplicates</h3>
            <p className="reconcile-description">
              Automatically find and merge duplicate people based on matching names and dates
            </p>
          </div>
          <button
            className="reconcile-button"
            onClick={handleReconcile}
            disabled={reconciling}
          >
            {reconciling ? 'Searching...' : '🔍 Find Duplicates'}
          </button>
        </div>

        {reconcileError && (
          <div className="reconcile-error">
            <strong>Error:</strong> {reconcileError}
          </div>
        )}

        {reconcileResult && (
          <div className="reconcile-results">
            <div className="result-summary">
              <div className="result-item">
                <span className="result-label">Candidates Found:</span>
                <span className="result-value">{reconcileResult.candidates_found}</span>
              </div>
              <div className="result-item">
                <span className="result-label">Exact Matches:</span>
                <span className="result-value">
                  {reconcileResult.candidates_above_threshold}
                </span>
              </div>
              <div className="result-item success">
                <span className="result-label">Merged:</span>
                <span className="result-value">{reconcileResult.duplicates_merged}</span>
              </div>
              {reconcileResult.skipped > 0 && (
                <div className="result-item">
                  <span className="result-label">Skipped:</span>
                  <span className="result-value">{reconcileResult.skipped}</span>
                </div>
              )}
            </div>
            {reconcileResult.errors.length > 0 && (
              <div className="reconcile-errors">
                <strong>Errors:</strong>
                <ul>
                  {reconcileResult.errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="people-table-container">
        <div className="table-header">
          <div className="select-all">
            <label>
              <input
                type="checkbox"
                checked={allSelected}
                onChange={handleSelectAll}
                disabled={filteredPeople.length === 0}
              />
              Select All ({filteredPeople.length})
            </label>
          </div>
          <div className="selection-info">
            {selectedPeople.size > 0 && <span>{selectedPeople.size} selected</span>}
          </div>
        </div>

        <div className="people-table">
          {filteredPeople.length === 0 ? (
            <div className="empty-state">
              <p>No people found matching filter</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th className="checkbox-col"></th>
                  <th>Name</th>
                  <th>Birth Year</th>
                  <th>Death Year</th>
                  <th>Current Family</th>
                  <th>Family Side</th>
                </tr>
              </thead>
              <tbody>
                {filteredPeople.map((person) => (
                  <tr
                    key={person.id}
                    className={selectedPeople.has(person.id) ? 'selected' : ''}
                  >
                    <td className="checkbox-col">
                      <input
                        type="checkbox"
                        checked={selectedPeople.has(person.id)}
                        onChange={() => handleTogglePerson(person.id)}
                      />
                    </td>
                    <td className="person-name">{person.primary_name}</td>
                    <td>{person.birth_year || '-'}</td>
                    <td>{person.death_year || '-'}</td>
                    <td>
                      {person.family_name ? (
                        <span className="family-badge">{person.family_name}</span>
                      ) : (
                        <span className="unassigned">Unassigned</span>
                      )}
                    </td>
                    <td>
                      {person.family_side ? (
                        <span className="side-badge">{person.family_side}</span>
                      ) : (
                        '-'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
