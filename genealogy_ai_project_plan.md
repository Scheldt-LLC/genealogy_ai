# Genealogy AI – Project Plan

## 1. Project Overview

This project ingests scanned historical family documents (typed, handwritten, photocopied), extracts genealogical information using OCR and LLMs, and builds a structured, auditable family tree.

**Core principles:**

- Preserve original source documents forever
- Separate *ground truth* from *AI-derived interpretations*
- Human-in-the-loop by default
- Open-source, local-first, cloud-optional

The system is designed to work entirely locally but can later be adapted to cloud providers (Azure, etc.) via adapters.

---

## 2. High-Level Architecture

```
Scanned PDFs / Images
        ↓
      OCR
        ↓
  Raw Text + Blocks
        ↓
 Entity Extraction Agent
        ↓
 Structured Data (SQLite)
        ↓
 Reconciliation Agent
        ↓
  Family Tree Queries

Parallel:
OCR Text → Chunking → Embeddings → Vector DB (Chroma)
```

---

## 3. Technology Stack (Open-Source First)

### Core

- **Python 3.11+**
- **LangChain** – agent orchestration
- **SQLite** – structured data (facts)
- **Chroma** – vector database (semantic recall)

### OCR

- **Tesseract** (default)
- Optional: PaddleOCR (better handwriting)

### LLM Providers (configurable)

- OpenAI
- Anthropic
- Ollama / local models

---

## 4. Data Storage Model

### 4.1 Ground Truth (Files)

- Original scans (PDF / image)
- OCR JSON output

Stored on disk and never mutated.

---

### 4.2 Structured Database (SQLite)

**documents**

- id
- source
- page
- ocr\_text

**people**

- id
- primary\_name
- notes
- confidence

**names**

- person\_id
- name

**events**

- person\_id
- type (birth, death, marriage)
- date
- place
- confidence

**relationships**

- source\_person
- target\_person
- type (parent, spouse, child)
- confidence

This is the *source of truth*.

---

### 4.3 Vector Database (Chroma)

Stored items:

- OCR text chunks
- Page summaries
- Person summaries
- Notes / hypotheses

**Never** store canonical facts here.

---

## 5. Agent Design

### Agent 1 – OCR Ingestion

**Input:** PDF / image **Output:** OCR text + chunks

Responsibilities:

- Run OCR
- Save raw OCR output
- Chunk text
- Store chunks in Chroma

---

### Agent 2 – Entity Extraction

**Input:** OCR text **Output:** Structured JSON

Extract:

- People
- Names (including variants)
- Dates (exact / approximate)
- Places
- Relationships

Rules:

- Do not invent facts
- Use confidence scores
- Preserve original spellings

Stores results in SQLite.

---

### Agent 3 – Reconciliation Agent

**Input:** New people/events **Uses:** Vector DB search

Responsibilities:

- Detect possible duplicates
- Suggest merges
- Flag ambiguities

❌ Does NOT auto-merge without human approval.

---

## 6. CLI Design (Initial Interface)

All functionality must be accessible via CLI.

### Commands

```bash
geneai ingest scans/*.pdf
geneai extract
geneai reconcile
geneai tree --person "John Byrne"
geneai export --format gedcom
```

CLI-first keeps scope manageable and encourages contributions.

---

## 7. Repository Structure

```
genealogy-ai/
├── ingestion/
│   ├── ocr.py
│   ├── chunking.py
├── agents/
│   ├── extract_entities.py
│   ├── reconcile_people.py
├── storage/
│   ├── sqlite.py
│   ├── chroma.py
├── schemas/
│   ├── person.json
│   ├── event.json
├── prompts/
│   ├── extraction.md
│   ├── reconciliation.md
├── cli.py
├── config.py
└── README.md
```

---

## 8. Development Phases

### Phase 1 – MVP (Local)

- OCR ingestion
- Entity extraction
- SQLite storage
- Chroma embeddings
- Basic CLI queries

### Phase 2 – Accuracy & Review

- Confidence thresholds
- Manual review tools
- Duplicate detection improvements

### Phase 3 – UI

- Web-based review UI
- Tree visualization
- Source citation viewer

### Phase 4 – Cloud Adapters (Optional)

- Azure AI Vision
- Azure AI Search
- Azure Foundry Agents

---

## 9. Open Source Guidelines

- License: MIT or Apache 2.0
- No required cloud services
- Clear contributor docs
- Transparent prompts and schemas

---

## 10. Success Criteria

- Every fact links back to a source
- Ambiguity is visible, not hidden
- New documents can be added without breaking existing data
- Data is exportable (GEDCOM)

---

## 11. Notes for Interns / Agents

- Never delete raw data
- Never auto-correct spellings without recording originals
- Confidence scores matter
- Ask for human input when unsure

This project values correctness and traceability over speed.

