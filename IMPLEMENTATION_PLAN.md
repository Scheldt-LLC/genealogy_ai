# Implementation Plan: Family Tree Separation & Enhanced Document Linking

## Overview

Add two major features to the genealogy application:
1. **Multiple Family Trees**: Separate people into distinct lineages (father's, mother's paternal, mother's maternal)
2. **Enhanced Document Links**: Track all documents where a person appears, including portraits and mentions

## Key Design Decisions (Based on User Preferences)

- **Family Separation**: Add `family_name` and optional `family_side` fields to Person table (e.g., family_name="scheldt", family_side="paternal")
- **Family Assignment at Upload**: User selects family when uploading - all extracted people automatically tagged
- **Document Linking**: Create new PersonDocument junction table for many-to-many relationships
- **Image Handling**: Add `document_type` field to Document table to distinguish portraits from records

## Database Schema Changes

### 1. Add `family_name` and `family_side` to Person Table
```python
family_name = Column(String, nullable=True, index=True)  # User-defined: "scheldt", "byrnes", "gilbert"
family_side = Column(String, nullable=True)  # Optional: "maternal" or "paternal"
```

**Why two fields?**
- `family_name` - Custom family identifier (required for family tracking)
- `family_side` - Optional maternal/paternal tag for filtering and organization

### 2. Add `document_type` to Document Table
```python
document_type = Column(String, nullable=True, index=True)
# Values: "census", "birth_certificate", "portrait", "photograph", etc.
```

### 3. Create PersonDocument Junction Table
```python
class PersonDocument(Base):
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    link_type = Column(String, nullable=False)  # "extracted_from", "mentioned_in", "portrait_of"
    notes = Column(Text, nullable=True)
    created_at = Column(String)
```

**Link Types**:
- `extracted_from` - Person originally extracted from this document
- `mentioned_in` - Person mentioned but not primary subject
- `portrait_of` - Document is a portrait/photo of person
- `signed_by`, `witness`, `about` - Other relationship types

## New Database Methods

**File**: `src/backend/genealogy_ai/storage/sqlite.py`

Add methods:
- `add_person_document_link(person_id, document_id, link_type, notes)`
- `remove_person_document_link(person_id, document_id)`
- `get_person_documents(person_id, link_type=None)` - Returns all documents for a person
- `get_document_people(document_id, link_type=None)` - Returns all people in a document
- `update_person_family(person_id, family_name, family_side=None)` - Update family assignment
- `update_document_type(document_id, document_type)`
- `get_people_by_family(family_name)` - Get all people in a family
- `get_family_list()` - Returns all unique family names with person counts

Update methods:
- `store_extraction()` - Auto-create PersonDocument links and assign family_name/family_side from document
- `merge_people()` - Preserve document links, family_name, and family_side when merging duplicates

## New API Endpoints

**File**: `src/backend/api/tree.py`

1. **Update GET /api/tree**
   - Add `?family_name=` query parameter to filter by family
   - Add `?family_side=` query parameter to filter by maternal/paternal
   - Include `family_name` and `family_side` in person response data

2. **GET /api/families**
   - List all unique family names with person counts
   - Include family_side breakdown for each family

3. **POST /api/people/<id>/family**
   - Assign a person to a family
   - Body: `{"family_name": "scheldt", "family_side": "paternal"}` (family_side optional)

4. **GET /api/people/<id>/documents**
   - Get all documents linked to a person
   - Optional `?link_type=` filter

5. **POST /api/people/<id>/documents**
   - Manually link a document to a person
   - Body: `{"document_id": 5, "link_type": "portrait_of", "notes": "Wedding photo"}`

6. **DELETE /api/people/<id>/documents/<doc_id>**
   - Remove a document link

**File**: `src/backend/api/documents.py`

7. **POST /api/documents/<id>/type**
   - Set/change document type
   - Body: `{"document_type": "census"}`

8. **GET /api/documents/<id>/people**
   - Get all people linked to a document

**File**: `src/backend/api/upload.py`

9. **Update POST /api/upload**
   - Add optional `document_type` form parameter (census, portrait, etc.)
   - Add optional `family_name` form parameter (user-defined family name)
   - Add optional `family_side` form parameter (maternal/paternal)
   - All extracted people automatically assigned to specified family
   - Auto-create PersonDocument links with "extracted_from" type

## Frontend Changes

### 1. Update Tree Component
**File**: `src/frontend/src/components/Tree.tsx`

- Add family list fetching from `/api/families`
- Add family filter dropdown above person selector
- Update tree data fetching to include `?family_id=` parameter
- Disable person selector when family filter is active

### 2. Update Upload Component
**File**: `src/frontend/src/components/Upload.tsx`

- Add document type dropdown with predefined options (census, portrait, etc.)
- Add family name selector (dropdown with existing families + "Create New" option)
- Add optional family side selector (maternal/paternal radio buttons)
- Include `document_type`, `family_name`, and `family_side` in upload form data
- Display family assignment in upload results
- Create new family names on the fly during upload

### 3. Create DocumentLinks Component (NEW)
**File**: `src/frontend/src/components/DocumentLinks.tsx`

- Display all documents linked to a person
- Show link type and notes for each document
- "View" button to open document
- "Unlink" button to remove link
- Can be embedded in person detail views

## Implementation Phases

### Phase 1: Database Layer (Week 1) - ✅ COMPLETE
1. ✅ Create migration script to add new tables/columns
2. ✅ Update SQLAlchemy models (PersonDocument, Person.family_name/family_side, Document.document_type)
3. ✅ Add 8 new database methods to GenealogyDatabase class
4. ✅ Update store_extraction() and merge_people() methods
5. ✅ Test with existing data

### Phase 2: API Endpoints (Week 2) - ✅ COMPLETE
1. ✅ Update GET /api/tree with family filtering
2. ✅ Add family management endpoints (3 new)
3. ✅ Add document linking endpoints (3 new)
4. ✅ Update upload endpoint for document_type, family_name, family_side
5. ✅ Update documents endpoints

### Phase 3: Frontend Basic (Week 3) - ✅ COMPLETE
1. ✅ Update Tree component with family filter
2. ✅ Update Upload component with document type selector
3. ✅ Display document types in document list

### Phase 4: Frontend Advanced (Week 4) - MEDIUM
1. Create DocumentLinks component
2. Create PersonDocumentManager for manual linking
3. Create FamilyManager for bulk assignments

### Phase 5: Auto-Detection (Week 5) - LOW
1. Auto-detect document type from OCR text using LLM
2. Auto-create "mentioned_in" links for all people detected
3. Suggest family groupings based on relationships

### Phase 6: Testing (Week 6) - MEDIUM
1. Unit tests for all database methods
2. Integration tests for API endpoints
3. Frontend component tests
4. Documentation updates

## Migration Strategy

### Backward Compatibility
- Keep Person.source_document_id field (mark deprecated)
- Migration auto-creates PersonDocument links from existing source_document_id
- Can remove source_document_id in future major version
- Existing people without family assignment will have family_name=None (unassigned)

### Migration Script
**File**: `alembic/versions/002_family_trees_and_document_links.py` (or manual script)

1. Add family_name column to people table (nullable, indexed)
2. Add family_side column to people table (nullable)
3. Add document_type column to documents table (nullable, indexed)
4. Create person_documents table with indexes
5. Migrate existing source_document_id to PersonDocument links
6. Backup database before migration

## Critical Files to Modify

1. **src/backend/genealogy_ai/storage/sqlite.py** - Core data models and methods
2. **src/backend/api/tree.py** - Family tree API endpoints
3. **src/backend/api/documents.py** - Document management endpoints
4. **src/backend/api/upload.py** - Upload with document type
5. **src/frontend/src/components/Tree.tsx** - Family filtering UI
6. **src/frontend/src/components/Upload.tsx** - Document type selection
7. **src/frontend/src/components/DocumentLinks.tsx** (NEW) - Document links UI

## Data Model Examples

### Family Names (User-Defined)
Examples based on your use case:
- `"scheldt"` - Your father's combined lineage (both grandparents)
- `"byrnes"` - Your mother's paternal line
- `"gilbert"` - Your mother's maternal line

### Family Side (Optional Tags)
- `"paternal"` - Father's side
- `"maternal"` - Mother's side
- `null` - No side specified (default)

### Example Person Records
```python
# Father's side (combined grandparents)
Person(name="John Scheldt", family_name="scheldt", family_side="paternal")

# Mother's side (separate families)
Person(name="Mary Byrnes", family_name="byrnes", family_side="maternal")
Person(name="Jane Gilbert", family_name="gilbert", family_side="maternal")

# Unassigned person
Person(name="Unknown Person", family_name=None, family_side=None)
```

### Document Types
- Vital: `birth_certificate`, `death_certificate`, `marriage_certificate`
- Government: `census`, `immigration_record`, `military_record`
- Legal: `will`, `deed`, `probate`
- Personal: `portrait`, `photograph`, `letter`, `diary`
- Other: `newspaper`, `other`

### Link Types
- `extracted_from` - Original extraction source
- `mentioned_in` - Named in document
- `portrait_of` - Subject of photo
- `signed_by` - Signed document
- `witness` - Witnessed document
- `about` - Document about person

## Testing Strategy

- Unit tests for all 8 new database methods
- API integration tests for all 9 new/updated endpoints
- Frontend component tests for family filtering and document linking
- End-to-end test scenarios:
  1. Upload document with family assignment → Extract entities → Verify family tags → View filtered tree
  2. Create multiple families (scheldt, byrnes, gilbert) → Upload docs to each → Filter tree by family
  3. Mix of assigned and unassigned people → Filter by family vs. "all"

## Simplified Workflow Example

**User's Workflow:**
1. Upload a census document from father's side
2. Select document_type = "census"
3. Select family_name = "scheldt" (or create new)
4. Select family_side = "paternal" (optional)
5. Click upload

**Backend Processing:**
1. OCR extracts text from document
2. Entity extraction finds people, events, relationships
3. All extracted people automatically get family_name="scheldt", family_side="paternal"
4. PersonDocument links created with link_type="extracted_from"
5. Document saved with document_type="census"

**Result:**
- All people from that document are now tagged as "scheldt" family
- User can filter tree view to show only "scheldt" family
- User can see all documents linked to each person

## Next Steps

1. ✅ Review and approve this plan
2. Start with Phase 1 (Database Layer)
3. Create migration script and test with existing data
4. Proceed through phases sequentially
