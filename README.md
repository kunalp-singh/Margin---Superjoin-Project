# Margin — A Fact Knowledge Layer

Margin is a web application that ingests PDF documents, extracts verifiable facts, grounds every fact in verbatim source text and page numbers, and determines whether facts across documents **corroborate**, **contradict**, or are **contextually reconciled** (different time periods, units, or scope). Facts that cannot be confidently classified are marked **uncertain** rather than forced into a bucket.

Built for the **Superjoin VIT 2026 Engineering Intern Assignment**.

---

## 1. Quick Start Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- (Optional) `GEMINI_API_KEY` from Google AI Studio. *Note: If no API key is provided, Margin runs on a deterministic rule-based evaluator out of the box.*

### Step 1: Clone & Setup Backend
```bash
# Clone the repository
git clone https://github.com/your-username/Margin-Superjoin.git
cd Margin-Superjoin

# Create Python Virtual Environment & Install Dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# (Optional) Copy environment template and add your Gemini API key
cp .env.example .env
```

### Step 2: Setup Frontend
```bash
cd frontend
npm install
cd ..
```

### Step 3: Run the Application
In terminal window 1 (Backend):
```bash
source venv/bin/activate
uvicorn backend.app.main:app --port 8000 --reload
```

In terminal window 2 (Frontend):
```bash
cd frontend
npm run dev
```

Open your browser at **`http://localhost:3000`**.

---

## 2. Seed Demo Data & 4 Evidence Cases

Upload multiple source PDFs from the same reporting set to demonstrate the four relationship cases:

1. **Corroboration Across Phrasings**: equivalent values with different wording or units.
2. **Genuine Contradiction**: conflicting values for the same entity, metric, period, and scope.
3. **Contextual Reconciliation**: differing values explained by time period, unit, or scope.
4. **Extraction/Reasoning Ambiguity**: a claim with missing metric, entity, period, or other referent is marked **uncertain**.

Click the **"Review 4 Cases"** button in the header for 1-click navigation to inspect any case.

---

## 3. Technical Approach & Architecture

```
PDF Upload ──► PyMuPDF Parsing ──► Sentence Segmentation ──► Gemini Fact Extraction
                                                                      │
SQLite Storage ◄── Gemini Relationship ◄── Candidate Retrieval ◄──────┘
(Incremental)     Reasoning Trace       (sentence-transformers)
```

- **Flexible JSON Attribute Schema**: Facts use a JSON column for `attributes` (`{entity, metric, value, unit, period, scope, qualifier}`) allowing new attribute types to appear dynamically without database migrations.
- **Local Candidate Search**: Uses `sentence-transformers` (`all-MiniLM-L6-v2`) and cosine similarity to retrieve top-$k$ candidate pairs prior to LLM evaluation, avoiding $O(n^2)$ API calls.
- **Structured Reasoning Traces**: Every relationship edge records an explicit step-by-step logic trace (`same_entity`, `same_metric`, `same_period`, `same_unit`, `reconciliation_dimension`) powering the **"Why?"** UI panel.
- **Incremental Ingestion**: Adding new PDFs appends facts and relationship edges into SQLite without wiping existing documents. An additive SQLite migration records a pipeline version and durable parse/extract/verify/persist/match timeline for every attempt; failed documents can be reprocessed from the API.
- **Layout-aware grounding**: PyMuPDF blocks, bounding boxes, table regions, and validated character offsets are retained. Atomic clauses and malformed-table uncertainty prevent a page artifact from becoming a fact.
- **Compatibility matching**: Candidate retrieval blocks incomparable entities/metrics before semantic scoring. Relationship reasoning exposes a six-dimension evidence checklist and derives confidence from those checks.

### AI Tools Used
- **Gemini 2.0 Flash (`google-genai` SDK)**: Used for structured JSON fact extraction, grounding verification, and multi-factor relationship reasoning.
- **Antigravity (Google DeepMind Agentic Coding Assistant)**: Used for architecture design, backend pipeline implementation, custom Tailwind design system creation, and test verification.

---

## 4. Design System — "Ink + Teal + Paper"

- **Color Tokens**:
  - `BACKGROUND`: `#F6F7F4` (soft cool-paper)
  - `SURFACE`: `#FFFFFF`
  - `PRIMARY TEXT`: `#202A2E` (deep ink)
  - `SECONDARY TEXT`: `#687277`
  - `BORDER`: `#DDE2E0`
  - `PRIMARY ACCENT`: `#287C78` (sophisticated teal)
  - `ACCENT LIGHT`: `#E2F0EE`
  - `ACCENT DARK`: `#1E625F`

- **Relationship Palette**:
  - **Corroborated** (Teal): background `#E2F0EE`, text `#286B67`, icon `#287C78`
  - **Contradicted** (Terracotta): background `#F4E6E2`, text `#92564E`, icon `#A96359`
  - **Reconciled** (Amber): background `#F4EDDC`, text `#896D35`, icon `#A88343`
  - **Uncertain** (Blue-grey): background `#E9EDF0`, text `#65727A`, icon `#71808A`

- **Typography**: **Inter** for UI controls/labels and **Source Serif 4** for verbatim grounded source quotes.

---

## 5. Limitations & Future Work

1. **OCR Support**: Current parser uses PyMuPDF for text-native PDFs. Scanned image-only PDFs can be integrated using Tesseract or Gemini Vision API.
2. **Hierarchical Document Navigation**: Adding a built-in PDF viewer canvas with bounding box overlays for visual document highlighting.
3. **Graph Clustering**: Grouping large clusters of related claims into topic sub-graphs for enterprise-scale corpora.
