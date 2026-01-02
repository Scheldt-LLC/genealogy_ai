import { useEffect, useState } from 'react'
import ReactFlow, {
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node,
  type Edge,
} from 'reactflow'
import 'reactflow/dist/style.css'
import './Tree.css'

interface Person {
  id: number
  name: string
  birth_date: string | null
  birth_place: string | null
  death_date: string | null
  death_place: string | null
  family_name: string | null
  family_side: string | null
}

interface Relationship {
  id: number
  source_id: number
  target_id: number
  type: string
}

interface TreeData {
  success: boolean
  people: Person[]
  relationships: Relationship[]
}

interface PersonOption {
  id: number
  name: string
  birth_year: number | null
}

interface Family {
  family_name: string
  person_count: number
  paternal_count: number
  maternal_count: number
  unspecified_count: number
}

export default function Tree() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [people, setPeople] = useState<PersonOption[]>([])
  const [selectedPersonId, setSelectedPersonId] = useState<number | null>(null)
  const [families, setFamilies] = useState<Family[]>([])
  const [selectedFamily, setSelectedFamily] = useState<string | null>(null)

  const fetchPeopleList = async () => {
    try {
      const response = await fetch('/api/tree/people')
      const data = await response.json()

      if (data.success) {
        setPeople(data.people)
      }
    } catch (err) {
      console.error('Failed to fetch people list:', err)
    }
  }

  const fetchFamilies = async () => {
    try {
      const response = await fetch('/api/families')
      const data = await response.json()

      if (data.success) {
        setFamilies(data.families)
      }
    } catch (err) {
      console.error('Failed to fetch families:', err)
    }
  }

  const fetchTreeData = async (personId?: number, familyName?: string) => {
    setLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      if (personId) params.append('person_id', personId.toString())
      if (familyName) params.append('family_name', familyName)

      const url = params.toString() ? `/api/tree?${params.toString()}` : '/api/tree'
      const response = await fetch(url)
      const data: TreeData = await response.json()

      if (data.success) {
        buildTree(data.people, data.relationships)
      } else {
        setError('Failed to load tree data')
      }
    } catch (err) {
      setError('Failed to fetch tree data: ' + (err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const buildTree = (peopleData: Person[], relationshipsData: Relationship[]) => {
    if (peopleData.length === 0) {
      setNodes([])
      setEdges([])
      return
    }

    // Create a map of person ID to their relationships
    const personRelationships = new Map<number, { parents: number[], children: number[], spouses: number[] }>()

    peopleData.forEach(person => {
      personRelationships.set(person.id, { parents: [], children: [], spouses: [] })
    })

    relationshipsData.forEach(rel => {
      const sourceRels = personRelationships.get(rel.source_id)
      const targetRels = personRelationships.get(rel.target_id)

      if (rel.type === 'parent') {
        // source is child, target is parent
        sourceRels?.parents.push(rel.target_id)
        targetRels?.children.push(rel.source_id)
      } else if (rel.type === 'spouse') {
        sourceRels?.spouses.push(rel.target_id)
        targetRels?.spouses.push(rel.source_id)
      }
    })

    // Simple layout algorithm - organize by generation
    const generations = new Map<number, number>() // person ID -> generation level
    const positioned = new Set<number>()

    // Find root people (those without parents)
    const roots = peopleData.filter(p => {
      const rels = personRelationships.get(p.id)
      return rels && rels.parents.length === 0
    })

    // BFS to assign generations
    const assignGeneration = (personId: number, level: number) => {
      if (positioned.has(personId)) return
      positioned.add(personId)
      generations.set(personId, level)

      const rels = personRelationships.get(personId)
      if (rels) {
        // Children are one generation down
        rels.children.forEach(childId => assignGeneration(childId, level + 1))
      }
    }

    // Start from roots
    if (roots.length > 0) {
      roots.forEach(root => assignGeneration(root.id, 0))
    } else {
      // No clear roots, just use first person
      assignGeneration(peopleData[0].id, 0)
    }

    // Assign generation 0 to any remaining people
    peopleData.forEach(p => {
      if (!positioned.has(p.id)) {
        assignGeneration(p.id, 0)
      }
    })

    // Position nodes
    const generationCounts = new Map<number, number>()
    const generationPositions = new Map<number, number>()

    // Count people per generation
    generations.forEach((gen) => {
      generationCounts.set(gen, (generationCounts.get(gen) || 0) + 1)
    })

    // Create nodes
    const newNodes: Node[] = peopleData.map(person => {
      const generation = generations.get(person.id) || 0
      const genCount = generationCounts.get(generation) || 1
      const genPosition = generationPositions.get(generation) || 0
      generationPositions.set(generation, genPosition + 1)

      const x = (genPosition - genCount / 2) * 300 + 400
      const y = generation * 200 + 100

      const birthYear = person.birth_date ? person.birth_date.split('-')[0] : '?'
      const deathYear = person.death_date ? person.death_date.split('-')[0] : person.death_date === null ? '' : '?'
      const lifespan = deathYear ? `${birthYear}–${deathYear}` : `b. ${birthYear}`

      return {
        id: person.id.toString(),
        type: 'default',
        data: {
          label: (
            <div className="person-node">
              <div className="person-name">{person.name}</div>
              <div className="person-dates">{lifespan}</div>
              {person.birth_place && (
                <div className="person-location">{person.birth_place}</div>
              )}
            </div>
          ),
        },
        position: { x, y },
      }
    })

    // Create edges
    const newEdges: Edge[] = relationshipsData.map(rel => ({
      id: `e${rel.id}`,
      source: rel.type === 'parent' ? rel.target_id.toString() : rel.source_id.toString(),
      target: rel.type === 'parent' ? rel.source_id.toString() : rel.target_id.toString(),
      type: rel.type === 'spouse' ? 'default' : 'smoothstep',
      animated: false,
      style: {
        stroke: rel.type === 'spouse' ? '#ff6b6b' : '#888',
        strokeWidth: 2,
      },
      markerEnd: rel.type !== 'spouse' ? {
        type: MarkerType.ArrowClosed,
        color: '#888',
      } : undefined,
      label: rel.type === 'spouse' ? '💑' : undefined,
    }))

    setNodes(newNodes)
    setEdges(newEdges)
  }

  useEffect(() => {
    fetchPeopleList()
    fetchFamilies()
    fetchTreeData()
  }, [])

  const handleFamilySelect = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const familyName = event.target.value || null
    setSelectedFamily(familyName)
    setSelectedPersonId(null) // Clear person selection when family changes
    fetchTreeData(undefined, familyName || undefined)
  }

  const handlePersonSelect = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const personId = event.target.value ? parseInt(event.target.value) : null
    setSelectedPersonId(personId)
    fetchTreeData(personId || undefined, selectedFamily || undefined)
  }

  const handleShowAll = () => {
    setSelectedPersonId(null)
    setSelectedFamily(null)
    fetchTreeData()
  }

  if (loading) {
    return (
      <div className="tree-container">
        <div className="tree-loading">Loading family tree...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="tree-container">
        <div className="tree-error">Error: {error}</div>
      </div>
    )
  }

  if (nodes.length === 0) {
    return (
      <div className="tree-container">
        <div className="tree-empty">
          <p>No family data yet.</p>
          <p>Upload documents to build your family tree!</p>
        </div>
      </div>
    )
  }

  return (
    <div className="tree-container">
      <div className="tree-controls">
        <div className="tree-filter">
          <label htmlFor="family-select">Filter by family:</label>
          <select
            id="family-select"
            value={selectedFamily || ''}
            onChange={handleFamilySelect}
          >
            <option value="">All families</option>
            {families.map(family => (
              <option key={family.family_name} value={family.family_name}>
                {family.family_name} ({family.person_count} {family.person_count === 1 ? 'person' : 'people'})
              </option>
            ))}
          </select>
        </div>
        <div className="tree-filter">
          <label htmlFor="person-select">Focus on person:</label>
          <select
            id="person-select"
            value={selectedPersonId || ''}
            onChange={handlePersonSelect}
          >
            <option value="">All people ({people.length})</option>
            {people.map(person => (
              <option key={person.id} value={person.id}>
                {person.name} {person.birth_year ? `(b. ${person.birth_year})` : ''}
              </option>
            ))}
          </select>
          {(selectedPersonId || selectedFamily) && (
            <button onClick={handleShowAll} className="show-all-btn">
              Show All
            </button>
          )}
        </div>
      </div>
      <div className="tree-view">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          attributionPosition="bottom-left"
        >
          <Controls />
          <Background />
        </ReactFlow>
      </div>
    </div>
  )
}
