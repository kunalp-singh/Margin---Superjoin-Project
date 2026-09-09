# Margin — A Fact Knowledge Layer

Margin ingests PDF documents, extracts grounded facts, and explains how claims across documents corroborate, contradict, reconcile, or remain uncertain.

## 1. Setup and Run Instructions

### Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer and npm
- A Gemini API key from [Google AI Studio](https://ai.google.dev/) (optional; the local rule-based path works without one)

### Backend setup

From the repository root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

Set `GEMINI_API_KEY` in `.env` if Gemini verification and reasoning are desired. The other supported variables are `DATABASE_URL`, `DISABLE_GEMINI`, `GEMINI_MODEL_NAME`, `PIPELINE_VERSION`, `GEMINI_TIMEOUT_SECONDS`, `GEMINI_MAX_RETRIES`, `CANDIDATE_SIMILARITY_THRESHOLD`, and `TOP_K_CANDIDATES`. The default database is SQLite at `data/margin.db`; tables and additive migrations are created automatically when the API starts.

Start the backend from the repository root:

```bash
source venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API is available at `http://localhost:8000` and its OpenAPI documentation is at `http://localhost:8000/docs`.

### Frontend setup

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`, then use the upload action to add one or more PDFs. The API alternative is:

```bash
curl -F "file=@/path/to/document.pdf" http://localhost:8000/api/documents
```

This repository does not commit PDFs or populated database data. A fresh clone therefore starts empty; upload the assignment PDFs through the UI or API to populate it.

## 3. Approach

I interpreted a Fact Knowledge Layer as more than a collection of extracted numbers. A useful fact must retain its verbatim source evidence, page number, character span, attributes, and uncertainty state. A useful relationship must explain why two facts are comparable and why the result is corroboration, contradiction, reconciliation, or uncertainty.

The current pipeline is:

```text
PDF layout parsing
  -> structural validation and clause-level segmentation
  -> local candidate extraction
  -> optional Gemini verification
  -> local embedding candidate retrieval and compatibility filtering
  -> checklist-based relationship classification
  -> SQLite persistence and API/UI presentation
```

The structural validation boundary is intentional. PyMuPDF retains page blocks and bounding boxes, while the parser filters page furniture, validates source spans, keeps value/period/unit tuples together, and separates table-like regions from prose. Only candidates that pass this boundary are sent to Gemini for verification or semantic reasoning. This boundary was added after testing exposed page numbers, dense-table cells, and values from different clauses being incorrectly treated as facts. An LLM should not be the first component deciding whether raw, structurally ambiguous text is a fact.

Facts use a flexible JSON `attributes` field (`entity`, literal `metric`, `value`, `unit`, `period`, `scope`, and optional qualifiers) rather than a fixed set of database columns. This preserves metric definitions that differ across documents and allows new attributes without a schema migration. `normalized_signature` and embeddings are separate retrieval aids; they do not replace the literal metric label used for comparison.

Relationship classification evaluates entity, metric definition, period, unit, scope, and qualifier/context before assigning a type. A cheap compatibility filter blocks obviously invalid pairs, such as percentage and count values or distinct revenue definitions, before classification. Confidence is derived from the resolved evidence dimensions rather than being a fixed score per relationship category. Documents, facts, relationships, and pipeline stages carry a version so stale derived data can be reprocessed explicitly.

Key trade-offs:

- SQLite was chosen over a vector database because the assignment-scale corpus needs no separate infrastructure, while SQLite keeps incremental ingestion and local development simple.
- Deterministic local embeddings retrieve candidate pairs before any LLM call. This reduces cost and latency on Gemini's free tier, at the cost of recall that has not yet been benchmarked on a large corpus.
- Clause-level and layout-aware preprocessing is more complex than sending page text directly to an LLM, but it prevents period/value misalignment and makes table failures visible as uncertainty instead of silently producing a wrong fact.
- Gemini is optional. Local extraction and checklist rules keep the application usable without an API key, while Gemini can verify structurally valid facts and handle cases where deterministic normalization is insufficient.

AI tools used:

- Gemini (`google-genai`, configured by `GEMINI_MODEL_NAME`) for verification and relationship reasoning after structural validation.
- Antigravity, an agentic coding assistant, for implementation, refactoring, UI work, and validation support.

## 4. Limitations and Next Steps

### What does not work well yet

- Table detection depends on PDF layout metadata. Visually drawn or irregular tables can be marked uncertain when row and column associations cannot be proven; coverage of dense financial tables is therefore incomplete.
- Candidate retrieval uses a fixed similarity threshold and top-k value. Recall and precision have not been evaluated against a large, diverse document corpus.
- The local fallback embedding is deterministic and lightweight rather than a fully evaluated semantic embedding service. It is suitable for the current scale but may miss paraphrases.
- There is no comprehensive automated regression suite for extraction, the six-dimension classification checklist, or the four demo cases. Current validation is compile/build, smoke checks, and manual review of reprocessed documents.
- The repository does not include the starter PDFs, populated database, screenshots, or the assignment video. A reviewer must upload PDFs to reproduce the populated state.

### What would be built next

- Large PDFs: profile parsing and embedding work on representative large files, then add bounded batching and background-worker instrumentation where needed.
- Many PDFs: add corpus-level indexing and pagination, then benchmark candidate retrieval and relationship deduplication as the number of facts grows.
- Dynamic schema: retain the JSON attributes model, but add schema validation/versioning for newly observed attribute types and an admin view for migrations.
- Incremental ingestion is implemented: new documents append facts and cross-document relationships without clearing unrelated documents. The next step is stronger duplicate detection and relationship rebuild controls.
- Add automated fixtures for page-number rejection, multi-period clauses, malformed tables, metric-definition mismatches, unit incompatibility, and each required relationship category.
- Add a committed demo-data workflow or documented sample-PDF download step if redistribution rights permit it.
- Replace the video placeholder below with the final four-case walkthrough before submission:

```text
VIDEO_LINK: <add the final four-case demonstration URL here>
```

## 5. Additional Notes

No API keys are committed. Copy `.env.example` to `.env` and provide credentials locally; `.env`, databases, uploads, virtual environments, and build artifacts are ignored by Git.

The four required cases—corroboration, genuine contradiction, contextual reconciliation, and extraction/reasoning uncertainty—are supported by the UI and review-case endpoint, but the final submission video link still needs to be added above.
