# Entity Building Pipeline - Implementation Summary

## Overview

I've redesigned the entity extraction and building pipeline to be much more robust, addressing your concerns about entity completeness and accuracy. The new system extracts entities to staging tables first, consolidates them to build complete records, and only inserts to the database after review.

## Architecture Changes

### Old Pipeline (Immediate Insertion)
```
OCR → Extract → Insert to DB → Reconcile
```
**Problems:**
- Entities inserted immediately without consolidation
- Duplicate handling happened after insertion
- Middle names and alternate information could be lost
- No human review for uncertain matches

### New Pipeline (Staged with Review)
```
OCR → Extract → Stage → Consolidate → Match → Auto-approve (≥95%) → Human Review (< 95%) → Insert to DB
```
**Benefits:**
- Entities fully built before database insertion
- Complete consolidation of all extracted information
- Human-in-the-loop for uncertain matches
- Maximum data preservation

## Key Components

### 1. Staging Tables (sqlite.py)

Created four new tables to support the pipeline:

- **`pending_people`** - Extracted person entities awaiting consolidation
- **`pending_events`** - Extracted events linked to pending people
- **`pending_relationships`** - Extracted relationships awaiting resolution
- **`entity_matches`** - Proposed matches for human review

Each record includes:
- `extraction_batch_id` - Groups entities from the same upload
- `status` - pending, approved, or rejected
- All original extracted data preserved

### 2. Entity Builder Service (build_entities.py)

New `EntityBuilder` class that handles:

#### Stage Extraction
```python
builder.stage_extraction(
    extraction_result,
    batch_id=batch_id,
    document_id=doc_id,
    family_name=family_name,
    family_side=family_side
)
```
Stores extracted entities in staging tables without database insertion.

#### Consolidate Batch
```python
builder.consolidate_batch(batch_id)
```
Groups similar pending people together and merges their data:
- Chooses best primary name (mixed case > ALL CAPS, more words > fewer words)
- Preserves ALL name variants
- Collects ALL events from all grouped people
- Calculates average confidence
- Builds complete entity records

#### Find Matches
```python
builder.find_matches(batch_id)
```
Compares consolidated entities with existing people using:
- Token set ratio for name matching (handles middle names)
- Birth date comparison (very strong signal, weight: 3.0)
- Death date comparison (strong signal, weight: 2.0)
- Place comparison (supporting evidence, weight: 0.5)
- Maiden name detection (first name match + different last name)

#### Process Batch
```python
builder.process_batch(batch_id, auto_approve=True)
```
- Auto-approves matches ≥ 95% confidence
- Creates review tasks for matches < 95% confidence
- Returns counts and review IDs

### 3. Updated Upload Flow (upload.py)

Modified upload endpoint to use staging pipeline:

```python
# Generate unique batch ID
batch_id = generate_batch_id()

# Extract and stage entities
for ocr_result, doc_id in zip(ocr_results, document_ids):
    extraction_result = extractor.extract(...)
    counts = builder.stage_extraction(extraction_result, batch_id, doc_id, ...)

# Consolidate, match, and auto-approve
processing_result = builder.process_batch(batch_id, auto_approve=True)
```

Response now includes:
- `entities_staged` - Total entities extracted
- `entities_auto_approved` - Auto-merged (≥95% confidence)
- `entities_needs_review` - Needs human review (< 95%)
- `review_ids` - IDs of matches needing review

### 4. Entity Review API (entity_review.py)

Three new endpoints for human review:

#### GET `/api/entities/pending`
Returns all pending matches with:
- Match confidence and reasons
- Pending entity details (names, events, family info)
- Existing entity details (for comparison)

#### POST `/api/entities/approve/<match_id>`
Approves a match and merges entities:
- Adds all name variants to existing person
- Transfers all events
- Creates PersonDocument links
- Marks as approved

#### POST `/api/entities/reject/<match_id>`
Rejects a match and creates new person:
- Creates new person from pending entity
- Transfers all events
- Preserves all data
- Marks as rejected

#### GET `/api/entities/batches`
Lists all extraction batches with status summary.

### 5. Entity Review UI (EntityReview.tsx)

Beautiful React component for reviewing matches:

**Features:**
- Side-by-side comparison of pending vs existing entities
- Color-coded confidence badges (high/medium/low)
- Displays all names, events, family info
- Match reasons shown clearly
- One-click approve (merge) or reject (keep separate)
- Real-time updates

**Design:**
- Full dark mode support
- Responsive layout
- Clear visual distinction between pending (blue) and existing (green) entities
- Intuitive approve/reject buttons

## How It Works - Example Flow

### Upload a Document

1. User uploads a census record
2. OCR extracts text from all pages
3. LLM extracts entities from each page → JSON
4. **NEW:** All entities staged in `pending_people`, `pending_events`, etc.
5. **NEW:** Entities within batch are consolidated:
   - "HARRY SCHELDT" + "Harry Vernon Scheldt" → merged to "Harry Vernon Scheldt" with "HARRY SCHELDT" as variant
   - All birth dates, events, etc. combined
6. **NEW:** Consolidated entities compared to existing people:
   - "Harry Vernon Scheldt" birth 1950-01-15 matches existing "Harry Scheldt" birth 1950-01-15
   - Confidence: 96% (birth date match + name match)
   - **Auto-approved and merged** (≥95%)

7. **NEW:** Another entity "Vera Scheldt" vs "Vera Markwell":
   - First name match: "Vera" = "Vera"
   - Different last names (maiden/married)
   - Birth date match: 1952-03-10 = 1952-03-10
   - Confidence: 92% (below 95% threshold)
   - **Sent to review queue**

### Review Uncertain Matches

1. User clicks "Entity Review" tab
2. Sees pending match:
   ```
   92% confidence
   Match reasons: first name match: 1.00, exact birth date match

   [Extracted Entity]          [Existing Person]
   Vera Scheldt                Vera Markwell
   Birth: 1952-03-10           Birth: 1952-03-10
   ```
3. User reviews and clicks:
   - **"✓ Merge"** - Approves match, adds "Vera Scheldt" as married name variant
   - **"✗ Keep Separate"** - Rejects match, creates new person "Vera Scheldt"

## Benefits of New System

### 1. Complete Entity Building
- All extracted information preserved
- Best names chosen automatically
- All variants retained
- Events from multiple extractions combined

### 2. Smart Matching
- Handles middle names (Harry vs Harry Vernon)
- Handles maiden/married names (Vera Scheldt vs Vera Markwell)
- Birth dates as primary matching signal
- Weighted confidence scoring

### 3. Human-in-the-Loop
- Only uncertain matches (< 95%) need review
- Clear side-by-side comparison
- One-click approve or reject
- No data loss either way

### 4. Data Integrity
- Nothing inserted to DB until approved
- All staging data preserved
- Audit trail via batch IDs and status fields
- Can review batches and statistics

## Testing the New System

### 1. Start the Backend
```bash
cd /Users/keithscheldt/Code/genealogy_ai/src/backend
python app.py
```

The new staging tables will be created automatically on first run.

### 2. Start the Frontend
```bash
cd /Users/keithscheldt/Code/genealogy_ai/src/frontend
npm run dev
```

### 3. Upload a Document
1. Go to "Upload Documents" tab
2. Upload a census record or other genealogy document
3. Watch the response:
   ```json
   {
     "entities_staged": 5,
     "entities_auto_approved": 3,
     "entities_needs_review": 2,
     "message": "3 entities auto-approved, 2 need review"
   }
   ```

### 4. Review Pending Matches
1. Click "Entity Review" tab
2. See pending matches with confidence scores
3. Review each match side-by-side
4. Approve (merge) or Reject (keep separate)

### 5. Verify Results
1. Go to "Family Tree" tab
2. See that approved entities were properly merged
3. Check that rejected entities created new people
4. All data should be complete (middle names, variants, all events)

## Files Modified/Created

### Backend
- `src/backend/genealogy_ai/storage/sqlite.py` - Added staging tables
- `src/backend/genealogy_ai/agents/build_entities.py` - **NEW** Entity builder service
- `src/backend/api/entity_review.py` - **NEW** Review API endpoints
- `src/backend/api/upload.py` - Updated to use staging pipeline
- `src/backend/app.py` - Registered entity_review blueprint

### Frontend
- `src/frontend/src/components/EntityReview.tsx` - **NEW** Review UI component
- `src/frontend/src/components/EntityReview.css` - **NEW** Review UI styles
- `src/frontend/src/App.tsx` - Added "Entity Review" tab

## Configuration

### Auto-Approve Threshold
Default: 95% confidence

To change, update in `upload.py`:
```python
builder = EntityBuilder(db=db, auto_approve_threshold=0.95)  # Change this
```

### Name Matching Threshold
Default: 85% similarity

To change, update in `build_entities.py`:
```python
builder = EntityBuilder(db=db, name_threshold=0.85)  # Change this
```

## Next Steps

1. **Test with real data** - Upload some of your actual documents and see how the staging works
2. **Review matches** - Try the Entity Review UI and approve/reject some matches
3. **Tune thresholds** - Adjust confidence thresholds based on your data
4. **Monitor batches** - Use `/api/entities/batches` to see batch statistics
5. **Provide feedback** - Let me know what works well and what needs improvement

## API Documentation

### GET `/api/entities/pending`
Returns pending matches needing review.

### POST `/api/entities/approve/{match_id}`
Approve and merge a match.

### POST `/api/entities/reject/{match_id}`
Reject a match and create new person.

### GET `/api/entities/batches`
List all extraction batches with statistics.

---

This new system gives you complete control over entity building and ensures maximum data preservation and accuracy!
