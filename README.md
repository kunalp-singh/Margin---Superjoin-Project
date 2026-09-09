# Margin — Grounded facts across documents

Margin is a small web application that reads PDFs, extracts facts with source evidence, and compares facts across documents. Each result is either corroborated, contradicted, reconciled by context, or marked uncertain.

## 1. Setup and Run Instructions

### Requirements

- Python 3.11+
- Node.js 18+ and npm
- Gemini API key from [Google AI Studio](https://ai.google.dev/) (optional)

### Install

From the repository root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env
```

Set `GEMINI_API_KEY` in `.env` to enable Gemini verification. Without a key, the local extraction and rule-based classifier still run.

The default database is SQLite at `data/margin.db`. It is created and migrated automatically when the backend starts.

In terminal 1, start the API:

```bash
source venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

In terminal 2, install and start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:

- Web app: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`

Upload PDFs from the web app, or use the API:

```bash
curl -F "file=@/path/to/document.pdf" http://localhost:8000/api/documents
```

The repository intentionally does not include API keys, uploaded PDFs, or the local database. A fresh clone starts empty; upload the PDFs you want to compare.

## 3. Approach

### Problem framing

The goal is not just to find numbers in a PDF. A fact is useful only when a reviewer can answer: What does it mean? Where did it come from? Which period and scope does it cover? Can another document confirm or challenge it?

For that reason, Margin stores every fact with:

- the exact source quote;
- page number and character offsets;
- entity, literal metric label, value, unit, period, scope, and qualifiers;
- a normal or uncertain status; and
- a relationship explanation when it is compared with another fact.

### Architecture

The code is split into a few simple layers:

```text
PDF upload
   |
   v
backend/app/services/pdf_parser.py
  Layout-aware text blocks, page geometry, clauses, table regions
   |
   v
backend/app/services/gemini_service.py
  Structural checks -> local extraction -> optional Gemini verification
   |
   v
backend/app/services/embedder.py
  Candidate retrieval and cheap compatibility filtering
   |
   v
backend/app/services/gemini_service.py
  Entity/metric/period/unit/scope/qualifier checklist
   |
   v
backend/app/services/pipeline.py
  Versioned persistence and stage status
   |
   v
SQLite -> FastAPI -> Next.js UI
```

The important boundary is between structural extraction and semantic reasoning:

1. PyMuPDF reads text with layout information instead of using only a flat page string.
2. The parser keeps clauses and value/period/unit tuples together.
3. Header/footer numbers, invalid source spans, implausible percentages, and malformed table regions are rejected or marked uncertain.
4. Only structurally valid candidates reach Gemini.
5. Candidate pairs are filtered before any relationship classification. Percentages are not compared with counts, and clearly different metric definitions are not treated as the same metric.

This boundary was added after testing exposed realistic failures: page numbers being read as values, table columns being mixed up, and a period from one clause being attached to a value from another. The system is deliberately conservative: an uncertain fact remains visible for review but should not create a normal relationship.

### Data model and schema

The database is defined in `backend/app/db/models.py`.

#### `documents`

One row per uploaded PDF:

- `filename`, `file_path`, `uploaded_at`, `page_count`
- overall `status` and `error_message`
- current pipeline stage and per-stage JSON status
- `pipeline_version` and timestamps for reprocessing

#### `facts`

One grounded claim extracted from a document:

- foreign key to `documents`
- `source_quote`, `page_number`, `char_start`, `char_end`
- flexible JSON `attributes`
- `normalized_signature` and an optional embedding for retrieval
- `status` (`normal` or `uncertain`) and `uncertainty_reason`
- `pipeline_version`

The JSON attributes object usually contains:

```json
{
  "entity": "Delhivery",
  "metric": "Revenue from services",
  "value": "81,415",
  "unit": "INR crore",
  "period": "FY 2024",
  "scope": "consolidated",
  "qualifier": null
}
```

The metric label is kept literally because “Revenue”, “Revenue composition”, and “Market share” are not interchangeable. JSON also lets new fact types add fields without a database migration. The normalized signature is only a retrieval aid; it is not treated as proof that two metrics are identical.

#### `relationships`

One comparison between two facts:

- `fact_a_id` and `fact_b_id`
- `type`: `corroborated`, `contradicted`, `reconciled`, or `uncertain`
- evidence-derived `confidence`
- JSON `reasoning` containing the checklist, summary, steps, and reconciliation dimension
- `pipeline_version`

#### `pipeline_runs` and `pipeline_stages`

These tables make processing visible and recoverable. Each run records its version and outcome. Each stage records attempts, timestamps, errors, and details for parsing, extraction, verification, persistence, matching, and completion. Reprocessing removes a document’s derived facts and relationships, then rebuilds them with the current pipeline version.

### Relationship logic

Before a relationship is created, the system evaluates:

- same entity;
- same metric definition;
- same period;
- same unit;
- same scope; and
- same qualifier or context.

If all relevant dimensions agree and values agree, the result is corroborated. If all dimensions agree and values differ, it is contradicted. If one dimension such as time period or scope explains the difference, it is reconciled. If the evidence is incomplete, it stays uncertain.

### Trade-offs

- **SQLite instead of a vector database:** no extra service is needed, and incremental ingestion is simple. This is appropriate for the assignment scale, not a claim of unlimited scale.
- **Local embeddings before Gemini:** this reduces API calls and cost, but the lightweight fallback embedding has not been benchmarked on a large corpus.
- **Conservative validation:** some difficult tables become uncertain instead of producing a guess. This sacrifices recall to avoid confident misinformation.
- **Optional Gemini:** the application remains runnable without credentials, while Gemini can verify valid candidates and help with ambiguous semantic comparisons.

### AI tools

- Gemini through the `google-genai` SDK for fact verification and relationship reasoning.
- An agentic coding assistant was used during implementation and validation.

## 4. Limitations and Next Steps

### What does not work well yet

- Irregular tables without reliable layout information may be marked uncertain.
- Candidate threshold and top-k retrieval settings are not tuned against a large document collection.
- The local fallback embedding can miss some paraphrases.
- There is no full automated regression suite for every extraction and classification edge case.
- Starter PDFs, screenshots, and the final demo video are not included in the repository.

### What is already supported

- New PDFs can be uploaded without rebuilding unrelated documents.
- Facts and relationships are versioned and can be reprocessed.
- The JSON attributes field can hold new kinds of fact metadata.
- Pipeline stages and failures are visible through the API and UI.

### What I would build next

- Add automated fixtures for page-number rejection, multi-period clauses, malformed tables, metric mismatches, and all four demo cases.
- Benchmark retrieval and processing time on large PDFs and many-document corpora.
- Add stronger duplicate detection and relationship pagination for larger knowledge layers.
- Add a small demo-data workflow if the source PDFs can legally be redistributed.
- Add the final four-case video URL here before submission:

```text
VIDEO_LINK: <add the final demonstration URL>
```

## 5. Additional Notes

No API keys are committed. Copy `.env.example` to `.env`; local secrets, databases, uploads, virtual environments, and build artifacts are ignored by Git.

The UI supports the required review cases: corroboration, contradiction, contextual reconciliation, and uncertainty. The reviewer must upload suitable PDFs to reproduce populated examples.
