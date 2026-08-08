# NOVA CHEAL (MediSafe)

**An AI-powered drug safety assistant** — checks drug-drug interactions and explains drug information in plain English, backed by a curated pharmacology database, a deterministic resolver/interaction engine, a RAG retrieval layer, and an LLM agent (Cerebras) that explains and reasons about results without ever overriding them.

Built for HEAL-A-THON 2026 by Team NOVA, PES University.

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [High-Level Architecture](#2-high-level-architecture)
3. [How the Database Was Built](#3-how-the-database-was-built)
4. [Database Schema](#4-database-schema)
5. [Backend — FastAPI Application](#5-backend--fastapi-application)
6. [The Resolver — Turning Any Drug Name Into an RXCUI](#6-the-resolver--turning-any-drug-name-into-an-rxcui)
7. [The RAG Pipeline](#7-the-rag-pipeline)
8. [The Agent Layer — Orchestration](#8-the-agent-layer--orchestration)
9. [Cerebras — The LLM Provider](#9-cerebras--the-llm-provider)
10. [The Two Core Methods](#10-the-two-core-methods)
11. [Frontend — Nova UI](#11-frontend--nova-ui)
12. [Running the App](#12-running-the-app)
13. [Environment Variables](#13-environment-variables)
14. [Design Decisions & Safety Philosophy](#14-design-decisions--safety-philosophy)
15. [Known Limitations](#15-known-limitations)

---

## 1. What This Project Does

NOVA CHEAL answers two kinds of questions:

1. **"Is it safe to take Drug A and Drug B together?"** — the **Interaction Checker**.
2. **"What is Drug X, what's it for, and what should I watch out for?"** — the **Drug Information** lookup.

Both features work whether the user types a generic name (`warfarin`), a US brand (`Tylenol`), an Indian brand (`Dolo 650`, `Crocin Advance`), a combo product (`Combiflam`), or a misspelled name (`atrovastatin`). Underneath, every query is resolved to a standardized **RXCUI** (RxNorm Concept Unique Identifier) before anything is looked up, so `paracetamol`, `acetaminophen`, and `Crocin` all converge on the exact same underlying drug record.

The system is explicitly **not** a black-box chatbot. A SQLite database of curated, sourced pharmacology data is always the ground truth. The LLM (Cerebras) is only ever used to *explain* or *fill gaps* — it is never allowed to invent or override a clinical severity rating.

---

## 2. High-Level Architecture

```
                         ┌─────────────────────────┐
                         │   Next.js Frontend       │
                         │   (nova-ui)               │
                         │  Interaction Checker /    │
                         │  Drug Information tabs    │
                         └────────────┬──────────────┘
                                      │ REST (JSON)
                                      ▼
                         ┌─────────────────────────┐
                         │   FastAPI Backend         │
                         │   app/main.py              │
                         └────────────┬──────────────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 ▼                    ▼                     ▼
        routes_interaction     routes_drug_info      routes_health
                 │                    │
                 ▼                    ▼
       agent_controller.py    drug_info_service.py
        (orchestration)              │
                 │                   │
      ┌──────────┼──────────┐        │
      ▼          ▼          ▼        ▼
interaction  drug_info  retrieval  resolver_service.py
_service.py  _service.py _service.py (rxcui resolution,
 (DB truth)  (profiles)  (RAG chunks) fuzzy matching,
      │          │          │         combo drugs)
      └──────────┴──────────┴─────────────┬───────┘
                                           ▼
                                  app/db/database.py
                                  (SQLite: medisafe.db)
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │  llm_provider.py        │
                               │  (Cerebras — explains,   │
                               │   never overrides)       │
                               └───────────────────────┘
```

Everything downstream of the resolver reads from a single SQLite file, `medisafe.db`, which was generated **offline, once**, by a data pipeline notebook. The FastAPI server never writes clinical data at runtime — it is a read-heavy query and reasoning layer on top of a static, versioned dataset.

---

## 3. How the Database Was Built

`medisafe.db` is not hand-written — it's the output of an ETL pipeline (`Copy_of_medisafe_pipeline_v8.ipynb`) that merges four public pharmacology sources into one RXCUI-indexed SQLite file. This runs **once**, offline (originally on Google Colab, since DrugBank's XML dump alone is >1.5 GB), and the resulting `medisafe.db` + `india_combos.json` are the two artifacts the FastAPI backend actually loads at startup.

### 3.1 Data sources

| Source | What it provides |
|---|---|
| **RxNorm** (`RXNCONSO.RRF`, NLM full monthly release) | The canonical name ↔ RXCUI mapping. This is the backbone every other table is keyed against. |
| **DrugBank** (full XML database) | Per-drug clinical profiles (description, indication, mechanism of action, toxicity, pharmacodynamics, dosage, brand names) and raw drug-drug interaction text. |
| **ONC DDI / LLMDDI** (`gadevito/LLMDDI` GitHub repo, `public-PDDI-analysis` pickle data) | Pre-labelled high-priority and non-interruptive drug-drug interaction pairs — a clinically vetted severity signal that DrugBank's free-text descriptions don't reliably provide. |
| **RxTerms** (NLM) | Clean prescribable drug names, used to build the brand/generic resolver. |
| **Kaggle "11k Indian Medicine Details"** | Indian brand names, compositions, and manufacturer data — this is what lets the system understand `Dolo 650`, `Crocin`, `Combiflam`, etc. |

### 3.2 Pipeline stages

The notebook runs as an ordered sequence of cells, each stage writing into an in-memory `pandas.DataFrame` that feeds the next:

**Stage 1 — Parse `RXNCONSO.RRF` → `drug_alias`**
RxNorm's raw concept file is pipe-delimited with no header. The pipeline keeps only English-language (`LAT=ENG`), non-obsolete (`SUPPRESS != 'O'`) rows from a whitelist of trusted source vocabularies (`RXNORM`, `DRUGBANK`, `MMSL`, `MTHSPL`, `VANDF`, `NDDF`, `ATC`, `GS`, `SNOMEDCT_US`). Every surviving `(name, RXCUI)` pair becomes an alias row. For multi-word strength-bearing names like `"ibuprofen 200 mg oral tablet"`, the pipeline also indexes the bare first word (`ibuprofen`) so short queries still resolve.

**Stage 2 — Build `brand_resolver`**
Combines RxTerms prescribable names with the Kaggle India dataset to build a single-lookup table from *any* brand/product name (Indian or US) straight to an RXCUI, tagged with a `region` (`IN` / `US`). A shared `normalise()` function (dose-unit stripping via regex, form-word removal like `tablet`/`syrup`/`sr`/`xr`) and a `brand_root()` function (strips trailing suffix tokens like `plus`, `ds`, `forte`, `advance`, or a single trailing letter) turn noisy real-world product names like `"Zerodol SP"` or `"Crocin Advance"` into clean lookup keys (`zerodol`, `crocin`). This same normalisation logic is duplicated in the backend's `app/utils/text_utils.py` so that runtime queries are matched exactly the same way the index was built.

**Stage 3 & 5 — Stream-parse DrugBank XML → `drug_profiles` + raw interaction text**
DrugBank's full XML export is parsed with `lxml.etree.iterparse` (not loaded fully into memory — this file is huge) filtering to `small molecule` and `biotech` drug types. For each drug the pipeline extracts:
- `description`, `indication`, `mechanism-of-action`, `toxicity`, `pharmacodynamics` (each truncated to a bounded character length to keep row sizes sane)
- Dosage strings (strength | form | route)
- Drug class, preferring short category labels
- Up to 30 brand/product names
- Every `<drug-interaction>` block as a raw `(drug_a, drug_b, description)` text triple

Every parsed drug name is immediately resolved to an RXCUI via the same resolver logic (`name_to_rxcui`), and any brand names found are folded back into the alias table.

**Stage 4 — Build `interactions` (DrugBank + ONC DDI merge)**
This is the most clinically important stage:
1. The ONC DDI pickle files (cloned from the LLMDDI research repo) are loaded and filtered to `ONC-HighPriority` and `ONC-NonInteruptive` sources — pairs that already carry a vetted `HIGH` / `LOW` severity label.
2. DrugBank's raw free-text interaction descriptions are resolved to RXCUI pairs and run through a **regex-based severity classifier** — a cascading set of rules that flags language like *"contraindicated"*, *"life-threatening"*, *"increased risk of bleeding"*, or *"narrow therapeutic"* as `HIGH`; *"monitor"*, *"caution"*, *"dose adjustment"* as `MODERATE`; *"minor"*, *"unlikely"* as `LOW`; and anything with no matching pattern as `UNKNOWN`.
3. The two sources are merged: **ONC's clinically vetted severity always wins** where both exist; DrugBank contributes description text and fills in pairs ONC doesn't cover.
4. Every pair is stored with `rxcui_a < rxcui_b` (alphabetically ordered) so `(warfarin, aspirin)` and `(aspirin, warfarin)` are always the same row — no duplicate storage, and the runtime query checks both orderings anyway as a safety net.

**Stage 6 — Build `rag_chunks`**
For every resolved drug profile, the pipeline emits one text chunk per topic (`description`, `indication`, `mechanism_of_action`, `side_effects_and_toxicity`, `pharmacology`), skipping anything under 20 characters. Each chunk is formatted as:

```
Drug: <name>
Topic: <topic>
<text>
```

so the LLM always sees which drug and which kind of information it's reading, even with a small retrieval window. On top of the per-drug chunks, every `HIGH`/`MODERATE` interaction pair *that has a real description* (>30 characters) gets its own `interaction_context` chunk:

```
Drug pair: <drug A> + <drug B>
Severity: HIGH
Interaction: <description>
```

This is the table `retrieval_service.py` queries at runtime — it's a **structured, pre-computed retrieval corpus**, not a live embedding search. There is no vector database and no embedding model in this pipeline; retrieval is exact/LIKE-based SQL over `rxcui` or drug name, which is fast, deterministic, and cheap — a deliberate tradeoff given the project's time constraints and Cerebras's speed-oriented inference.

**Cell 10 — Write everything to SQLite**
All five DataFrames are written to `medisafe.db` in one pass, with indexes created on every foreign-key-like column (`rxcui`, `severity`, `topic`) for fast lookups. The final artifact for this project is roughly **421 MB**, containing **~1.37 million interaction pairs** and **9,004 Indian brand → ingredient mappings** (exported separately as `india_combos.json` for combo-drug resolution, e.g. `combiflam → [ibuprofen, paracetamol]`).

Because this pipeline is expensive to re-run (the DrugBank XML parse alone takes 3–6 minutes, RxNorm parsing ~1 minute, plus network calls to clone the ONC dataset), `medisafe.db` and `india_combos.json` are treated as **build artifacts, not source code** — they are `.gitignore`'d and must be placed manually in the backend folder before starting the server (see [Running the App](#12-running-the-app)). Two small helper scripts, `inject_curated.py` and `inject_curated_p2.py`, exist to patch in a short list of well-known, clinically important interactions (warfarin+NSAIDs, metformin+alcohol, statins+CYP3A4 inhibitors, SSRIs+tramadol, etc.) as a manual override layer in case DrugBank/ONC missed or under-classified them — these are marked with `source = 'curated_override'` in the `interactions` table so they're clearly distinguishable from the automated pipeline's output.

---

## 4. Database Schema

```sql
-- Every name/brand/synonym → RXCUI (many-to-many: one alias can map to multiple RXCUIs)
CREATE TABLE drug_alias (
    alias   TEXT NOT NULL,
    rxcui   TEXT NOT NULL,
    PRIMARY KEY (alias, rxcui)
);

-- Fast single-lookup brand table (Indian + US brands → RXCUI)
CREATE TABLE brand_resolver (
    input_name TEXT PRIMARY KEY,
    rxcui      TEXT NOT NULL,
    region     TEXT               -- 'IN' or 'US'
);

-- One row per canonical drug
CREATE TABLE drug_profiles (
    rxcui         TEXT,
    name          TEXT PRIMARY KEY,
    drug_class    TEXT,
    description   TEXT,
    indication    TEXT,
    mechanism     TEXT,
    side_effects  TEXT,
    pharmacology  TEXT,
    dosage        TEXT,
    brand_names   TEXT,           -- JSON-encoded list
    source        TEXT
);

-- Drug-drug interaction pairs, alphabetically ordered by RXCUI
CREATE TABLE interactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rxcui_a     TEXT NOT NULL,
    rxcui_b     TEXT NOT NULL,
    severity    TEXT CHECK(severity IN ('HIGH','MODERATE','LOW','UNKNOWN')),
    description TEXT,
    source      TEXT,
    UNIQUE(rxcui_a, rxcui_b)
);

-- Pre-chunked pharmacology text for the RAG / LLM context layer
CREATE TABLE rag_chunks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    rxcui      TEXT,
    drug_name  TEXT,
    topic      TEXT,
    chunk_text TEXT
);

CREATE INDEX idx_alias_rxcui    ON drug_alias(rxcui);
CREATE INDEX idx_inter_a        ON interactions(rxcui_a);
CREATE INDEX idx_inter_b        ON interactions(rxcui_b);
CREATE INDEX idx_inter_severity ON interactions(severity);
CREATE INDEX idx_profile_rxcui  ON drug_profiles(rxcui);
CREATE INDEX idx_rag_rxcui      ON rag_chunks(rxcui);
CREATE INDEX idx_rag_topic      ON rag_chunks(topic);
```

`india_combos.json` sits alongside the database as a plain JSON map (not a SQL table) because it's small and only needed at import time by the resolver:

```json
{
  "combiflam": ["ibuprofen", "paracetamol"],
  "dolo 650":  ["paracetamol"],
  "crocin":    ["paracetamol"]
}
```

---

## 5. Backend — FastAPI Application

The backend lives entirely under `app/` and is a standard layered FastAPI service:

```
app/
├── main.py                     ← FastAPI app, lifespan, CORS, router registration
├── config.py                   ← env-driven configuration
├── api/
│   ├── routes_interaction.py   ← POST /api/check_interaction
│   ├── routes_drug_info.py     ← GET  /api/drug_info
│   └── routes_health.py        ← GET  /health
├── agent/
│   └── agent_controller.py     ← orchestration layer (see §8)
├── services/
│   ├── interaction_service.py  ← deterministic DB interaction lookup
│   ├── drug_info_service.py    ← drug profile + brand-name resolution
│   ├── retrieval_service.py    ← RAG chunk retrieval
│   └── resolver_service.py     ← name → RXCUI resolution (combo, alias, brand, fuzzy)
├── llm/
│   └── llm_provider.py         ← Cerebras client, prompts, JSON parsing, fallbacks
├── db/
│   ├── database.py             ← thread-local SQLite connection (WAL mode)
│   └── queries.py               ← all raw SQL, no business logic
├── models/
│   └── schemas.py              ← Pydantic v2 request/response models
└── utils/
    ├── text_utils.py            ← normalise(), brand_root() — must match the pipeline exactly
    └── brand_filter.py          ← filters junk product descriptions out of brand_names
```

### 5.1 `main.py` and application lifespan

FastAPI's `lifespan` context manager is used instead of a global variable so the fuzzy-matching index is built **exactly once**, at process startup, and shared across every request/thread — not rebuilt on every call:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    n = build_fuzzy_index()   # loads every brand_resolver key into RAM
    yield
```

CORS is wide open (`allow_origins=["*"]`) for local development — this should be tightened before any real deployment.

### 5.2 Database connectivity

`app/db/database.py` opens one SQLite connection **per thread** (`threading.local()`), since Uvicorn/FastAPI dispatches sync request handlers onto a worker thread pool and SQLite connections aren't safe to share across threads without `check_same_thread=False`. The connection is tuned for a large, read-heavy file:

```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA cache_size=-64000")   # 64 MB page cache
conn.execute("PRAGMA temp_store=MEMORY")
```

`app/db/queries.py` holds every raw SQL statement as a small, isolated function — no business logic lives here, so the SQL surface area is easy to audit and reuse across services.

---

## 6. The Resolver — Turning Any Drug Name Into an RXCUI

`app/services/resolver_service.py` is arguably the most important piece of runtime logic — everything else (interaction checks, drug profiles, RAG retrieval) depends on correctly resolving whatever string the user typed into one or more RXCUIs. It mirrors the exact same normalisation logic used to *build* the index, so runtime lookups and the offline pipeline stay consistent.

Resolution runs through four strategies, **in priority order**, stopping at the first one that succeeds:

1. **Combo map** (`india_combos.json`) — checked first because a name like `combiflam` should resolve to *two* ingredient RXCUIs (`ibuprofen`, `paracetamol`), not one. Checked against the raw name, the normalised name, and the "brand root" (suffix-stripped) form.
2. **`drug_alias` exact/normalised lookup** — the RxNorm-derived canonical name table.
3. **`brand_resolver` exact/normalised lookup** — Indian + US brand names.
4. **Fuzzy fallback** — only as a last resort, using `rapidfuzz`'s `WRatio` scorer against every key in `brand_resolver` (loaded into memory once at startup by `build_fuzzy_index()`), with a configurable score cutoff (`FUZZY_CUTOFF = 94` at the API layer; the original pipeline/resolver default is 88 — the API config intentionally sets a stricter cutoff to reduce false-positive matches in a safety-critical tool).

The interaction and drug-info services layer additional strategies on top of the base resolver — e.g. walking the `drug_alias` table outward from a resolved RXCUI to catch INN synonym gaps (`paracetamol` ↔ `acetaminophen`), and looking up the **canonical profile RXCUI** directly from `drug_profiles` by name, since interactions are stored under a drug's canonical profile RXCUI rather than every product-specific RXCUI variant.

---

## 7. The RAG Pipeline

"RAG" here means **retrieval-augmented generation over a pre-built, structured chunk table** — not a live vector-embedding search. This was a deliberate design choice: pharmacology text doesn't change at runtime, so there's no need to embed and re-rank on every request. A simple, fast SQL lookup over `rag_chunks` gives the LLM grounded context in single-digit milliseconds.

`app/services/retrieval_service.py` implements the retrieval step:

```python
def retrieve_context(drug1, drug2, rxcui1=None, rxcui2=None) -> str:
    if rxcui1 and rxcui2:
        chunks = query_rag_chunks(rxcui1, rxcui2, limit=RAG_CHUNK_LIMIT)   # exact RXCUI match
    if not chunks:
        chunks = query_rag_chunks_by_name(drug1, drug2, limit=RAG_CHUNK_LIMIT)  # LIKE fallback
    return "\n\n---\n\n".join(chunks)
```

- **Primary path:** exact match on `rxcui IN (rxcui1, rxcui2)`, ordered so `interaction_context` chunks (which start with a capital letter and sort last alphabetically after topic names, but are prioritised via `ORDER BY topic DESC`) surface first.
- **Fallback path:** if no RXCUI is available (e.g. an unresolved drug name), falls back to a `LIKE '%name%'` match against `drug_name`.
- **Retrieval budget:** capped by `RAG_CHUNK_LIMIT` (default `6`) in `config.py`, keeping the prompt small enough to stay well inside Cerebras's low-latency response window.

The agent (§8) calls this **for every query** — not just unknown ones — because richer grounding produces a better plain-English explanation even when the database already has a confirmed severity.

---

## 8. The Agent Layer — Orchestration

`app/agent/agent_controller.py` is the orchestration brain of the system. It's the single entry point (`handle_interaction_query`) called by the `/api/check_interaction` route, and its job is to run every tool in the right order and decide **which LLM mode to invoke** based on what the database already knows.

```
handle_interaction_query(drug1, drug2)
│
├─ Step 1 — Deterministic DB check (interaction_service.check_interaction)
│           → severity ∈ {HIGH, MODERATE, LOW, UNKNOWN, NOT_FOUND}
│           → this value is NEVER overridden by the LLM
│
├─ Step 2 — Fetch drug profiles for both drugs (drug_info_service.get_drug_info)
│           → always run, used purely as extra LLM context
│
├─ Step 3 — RAG retrieval (retrieval_service.retrieve_context)
│           → always run — even for a KNOWN severity, richer context
│              produces a better plain-English explanation
│
└─ Step 4 — LLM call — mode depends on severity:
            • severity ∈ {HIGH, MODERATE, LOW}  → explain_known_interaction()
              (LLM simplifies a confirmed DB result — cannot change the verdict)
            • severity ∈ {UNKNOWN, NOT_FOUND}    → assess_unknown_interaction()
              (LLM reasons from pharmacology context and returns its own
               risk estimate, tagged as an AI advisory, not a DB fact)
```

This is the core safety guarantee of the whole system, stated directly in the code's own docstring: *"The DB result is NEVER overridden. The LLM only explains or fills gaps."* Every response also carries a different disclaimer depending on which path was taken — a soft "this was AI-simplified" note for known/confirmed interactions, versus a much stronger "⚠️ AI-generated advisory — not clinically validated" warning when the database had no answer and the LLM had to reason from context alone. The API response schema also exposes this distinction directly via `confidence: "known" | "dataset_missing"` and `source: "database" | "llm_fallback"`, so a consuming frontend can visually differentiate a verified fact from an AI estimate.

The agent is deliberately **not** a multi-step autonomous loop with dynamic tool selection — it's a fixed, auditable pipeline. Given this is a safety-sensitive medical tool, a deterministic sequence of "always check the database → always fetch context → conditionally call the LLM for explanation only" is far easier to reason about and test than a free-form agent that decides its own tool calls.

---

## 9. Cerebras — The LLM Provider

`app/llm/llm_provider.py` wraps the Cerebras Cloud SDK (`cerebras.cloud.sdk.Cerebras`) as the sole LLM backend, chosen for its very low-latency inference — important here because the whole request (DB lookup → RAG retrieval → LLM call) has to stay well under a one-minute response budget (`LLM_TIMEOUT = 30` seconds in `config.py`), and every request pays for a live LLM call, not just a cached lookup.

**Model:** `llama3.1-8b`, called via `client.chat.completions.create()` with `temperature=0.15` (kept low and near-deterministic — this is not a creative-writing task) and `max_tokens=400`.

The provider exposes **three distinct prompted behaviors**, all sharing one system prompt that constrains the model to ground its answer in the supplied context and never invent drug names or mechanisms:

| Function | Called when | What it does |
|---|---|---|
| `explain_known_interaction()` | DB severity is `HIGH`/`MODERATE`/`LOW` | Rewrites the confirmed DB result in plain English: what the severity means practically, why the interaction happens, and what the user should do. |
| `assess_unknown_interaction()` | DB severity is `UNKNOWN`/`NOT_FOUND` | Full reasoning pass from pharmacology context alone — estimates `HIGH / MODERATE / LOW / INSUFFICIENT_DATA`, explains mechanism, gives a recommendation, and must explicitly flag itself as an AI estimate. |
| `simplify_drug_info()` | Called by the drug-info route on every lookup | Rewrites DrugBank's dense clinical text (indication, mechanism, toxicity) into friendly patient language: `what_its_for`, `how_it_works`, `side_effects`, `safety_tip`. |

Every prompt asks Cerebras to respond in **strict JSON**, and `_parse_llm_json()` / `_parse_drug_info_json()` handle stripping stray Markdown code fences and gracefully degrading if the model doesn't return valid JSON — falling back to a regex severity extraction, or in the worst case a safe `"UNAVAILABLE"` response instructing the user to consult a professional. If `CEREBRAS_API_KEY` isn't set at all, the SDK client is simply never constructed and every LLM call short-circuits to the same safe fallback — the deterministic parts of the app (interaction checking, drug profiles) continue to work with zero LLM dependency.

---

## 10. The Two Core Methods

### 10.1 `POST /api/check_interaction` — Interaction Checker

**Request**
```json
POST /api/check_interaction
Content-Type: application/json

{
  "drug1": "warfarin",
  "drug2": "aspirin"
}
```

**What happens under the hood:**
1. Both names are resolved to RXCUIs via the resolver (combo map → alias → brand → fuzzy).
2. Every `(rxcui_a, rxcui_b)` pair across both resolved sets is checked against `interactions`, taking the worst severity found (with an early exit as soon as a `HIGH` match is found).
3. Drug profiles for both names are fetched for LLM context.
4. RAG chunks are retrieved for both RXCUIs.
5. The agent picks the LLM mode based on whether severity came back as a real DB value or `UNKNOWN`/`NOT_FOUND`.

**Response** (known-severity example)
```json
{
  "drug1": "warfarin",
  "drug2": "aspirin",
  "resolved_drug1": "warfarin",
  "resolved_drug2": "aspirin",
  "severity": "HIGH",
  "description": "Aspirin inhibits platelet aggregation and may displace warfarin from plasma proteins, significantly increasing bleeding risk.",
  "source": "database",
  "confidence": "known",
  "llm_assessment": {
    "risk_estimate": "HIGH",
    "reasoning": "Taking these together significantly raises your risk of serious bleeding..."
  },
  "warning": "This explanation was generated by AI to simplify a confirmed database result. Always consult a healthcare professional before changing your medications."
}
```

When the database has no confirmed entry, `source` becomes `"llm_fallback"`, `confidence` becomes `"dataset_missing"`, and the stronger advisory warning is attached instead — the frontend's `InteractionResult` component can key off `confidence` to visually distinguish a verified answer from an AI estimate.

### 10.2 `GET /api/drug_info` — Drug Information

**Request**
```
GET /api/drug_info?drug=dolo%20650
```

**What happens under the hood:**
1. `dolo 650` resolves through the combo/alias/brand/fuzzy chain to the `acetaminophen`/`paracetamol` RXCUI.
2. The profile is fetched directly by RXCUI; if that fails, the code walks the `drug_alias` table outward from every resolved RXCUI to find a matching profile (catches INN synonym gaps), then falls back to exact and finally fuzzy name matching against `drug_profiles`.
3. Brand names are collected from `brand_resolver` using **both** the resolved RXCUIs and every known synonym of the drug (so an `acetaminophen` profile also surfaces `paracetamol`-side Indian brands like Dolo and Crocin), with Indian brands sorted first. A `brand_filter.py` utility strips out junk DrugBank product descriptions (e.g. `"healthy accents pain relief"`) that aren't real brand names.
4. Cerebras rewrites the raw clinical fields into `plain_english` (`what_its_for`, `how_it_works`, `side_effects`, `safety_tip`).

**Response**
```json
{
  "name": "acetaminophen",
  "resolved_name": "acetaminophen",
  "drug_class": "Analgesic",
  "indication": "For the relief of mild to moderate pain and fever.",
  "mechanism": "Thought to act primarily in the central nervous system...",
  "side_effects": "Hepatotoxicity at high doses...",
  "pharmacology": "...",
  "dosage": "500 mg | tablet | oral",
  "description": "...",
  "brand_names": ["dolo 650", "crocin", "tylenol", "calpol"],
  "plain_english": {
    "what_its_for": "This medicine helps bring down fever and eases everyday aches and pains.",
    "how_it_works": "It works in your brain to turn down pain signals and reset your body's temperature control.",
    "side_effects": "Taken as directed it's very safe, but taking too much can seriously harm your liver.",
    "safety_tip": "Never exceed the labeled dose, and avoid alcohol while taking it."
  }
}
```

A `404` is returned if the drug can't be resolved through any strategy, with a message suggesting the user check spelling or try the generic name.

---

## 11. Frontend — Nova UI

`nova-ui/` is a Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS v4 single-page app.

```
nova-ui/
├── app/
│   ├── page.tsx           ← tabbed shell: Interaction Checker | Drug Information
│   └── layout.tsx
├── components/
│   ├── InteractionChecker.tsx   ← two drug-name inputs, calls /api/check_interaction
│   ├── InteractionResult.tsx    ← renders severity, LLM explanation, warning banner
│   ├── DrugInfo.tsx              ← single drug-name input, calls /api/drug_info
│   ├── DrugProfileCard.tsx       ← renders profile + plain-English summary
│   ├── ErrorAlert.tsx
│   ├── LoadingState.tsx
│   └── Navbar.tsx
├── lib/api.ts               ← typed fetch wrappers around the FastAPI backend
└── types/api.ts              ← shared TypeScript types mirroring the Pydantic schemas
```

The UI is a thin client — all resolution, database logic, RAG retrieval, and LLM orchestration happen server-side. The frontend's only job is to collect two drug names (or one, for the info lookup), call the appropriate endpoint via `NEXT_PUBLIC_API_URL`, and render the structured JSON response, including surfacing the `warning` and `confidence` fields prominently so users can tell a verified database fact apart from an AI-generated estimate.

---

## 12. Running the App

### Backend

```bash
cd medisafe_backend
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# add your CEREBRAS_API_KEY inside .env

# Place these two pipeline-generated artifacts inside the backend folder:
#   medisafe.db
#   india_combos.json

uvicorn app.main:app --reload --port 8000
```

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd nova-ui
npm install

# .env.local
echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000" > .env.local

npm run dev
```

- Web app: `http://localhost:3000`

### Usage
1. Open `http://localhost:3000`.
2. **Interaction Checker** tab — enter two drug names to check for interactions.
3. **Drug Information** tab — enter one drug name to view its full profile.

---

## 13. Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `DB_PATH` | `medisafe.db` | Path to the SQLite database produced by the pipeline. |
| `INDIA_COMBOS_PATH` | `india_combos.json` | Path to the combo-drug ingredient map. |
| `CEREBRAS_API_KEY` | *(empty)* | Cerebras Cloud API key. Without it, the app still runs — LLM calls degrade gracefully to a safe "consult a professional" fallback. |
| `NEXT_PUBLIC_API_URL` (frontend) | — | Base URL of the FastAPI backend, set in `nova-ui/.env.local`. |

Additional non-env tuning knobs live in `app/config.py`: `CEREBRAS_MODEL` (`llama3.1-8b`), `LLM_TIMEOUT` (30s), `RAG_CHUNK_LIMIT` (6 chunks), `FUZZY_CUTOFF` (94).

---

## 14. Design Decisions & Safety Philosophy

- **The database is ground truth; the LLM never overrides it.** Every response's `severity` value comes from `interactions`, never from the model. This is enforced structurally in `agent_controller.py`, not just by prompting.
- **Different disclaimers for different confidence levels.** A confirmed DB interaction gets a mild "AI-simplified" note; an LLM-only estimate gets a loud "⚠️ not clinically validated" warning. The API even exposes a machine-readable `confidence` field so the frontend can style these differently.
- **Retrieval is structured SQL, not embeddings.** Given the dataset is static and the topics are already well-labelled (`description`, `mechanism`, `interaction_context`, etc.), exact/LIKE lookups on `rag_chunks` are faster and more predictable than a vector search, at the cost of being less flexible for free-form questions outside the two supported workflows.
- **Cerebras was chosen for latency, not scale.** The whole request path — resolve, DB check, profile fetch, RAG retrieval, LLM call — has to complete comfortably inside normal user-facing response times, which shaped the choice of a fast open-weight model over a larger, slower one.
- **Curated overrides are transparent, not silent.** Manually injected interactions (`inject_curated.py` / `inject_curated_p2.py`) are tagged `source = 'curated_override'` in the database rather than merged invisibly into the automated pipeline output, so it's always possible to tell which rows came from the automated ETL versus a manual clinical patch.

---

## 15. Known Limitations

- `medisafe.db` and `india_combos.json` are build artifacts, not checked into version control — the pipeline notebook must be re-run (or the files obtained separately) before the backend can serve real data.
- The severity classifier used to label DrugBank's free-text interaction descriptions is regex/keyword-based, not a trained clinical NLP model — it's a reasonable heuristic, not a substitute for pharmacist review.
- RAG retrieval has no semantic search — a drug name that doesn't match any alias, brand, or fuzzy candidate simply returns no context, and the LLM falls back to reasoning with whatever profile data (if any) was found.
- The fuzzy-matching fallback (`rapidfuzz`, `WRatio`) can occasionally match unrelated but similarly-spelled drug names; the strict score cutoff (94) is a mitigation, not a guarantee.
- CORS is currently wide open (`allow_origins=["*"]`) for local development and should be restricted before any production deployment.
- This tool is **not a substitute for professional medical advice** — every response, whether database-sourced or AI-generated, carries an explicit disclaimer to that effect for exactly this reason.
