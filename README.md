# ClassSense: AI Teaching Assistant

> **ClassSense** is an AI teaching assistant that detects where students struggle in lecture audio/video, traces root prerequisite gaps using vector retrieval, and equips teachers with targeted pedagogical interventions and students with Socratic catch-up material.

---

## 🏛️ Monorepo Architecture

```
AI_PROJECT/
├── backend/
│   ├── alembic/                 # Database migrations (Alembic)
│   ├── app/
│   │   ├── api/v1/              # API router and endpoints (/health, /jobs, /lectures)
│   │   ├── core/                # Config (pydantic-settings), error envelope
│   │   ├── db/                  # Session, Base declarative class, mixins
│   │   ├── models/              # SQLAlchemy 2.x models for all 12 domain entities
│   │   ├── providers/           # Pure ABC interfaces + Mistral & Gemini adapters
│   │   ├── schemas/             # Pydantic v2 schemas carrying 3D coordinates (x, y, z)
│   │   ├── services/            # Background job runner & domain services
│   │   └── main.py              # FastAPI app factory with CORS & error handlers
│   ├── tests/                   # Backend test suite (pytest-asyncio)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # Strongly-typed fetch client with error envelope
│   │   ├── components/
│   │   │   ├── layout/          # Header, Sidebar, MobileDrawer, AppLayout
│   │   │   └── ui/              # Button, Card, Badge, Progress, Alert, Modal
│   │   ├── hooks/               # useNavigation (10 view IDs), useJobPolling
│   │   ├── services/            # Frontend services (jobService, lectureService)
│   │   ├── test/                # Vitest tests for 10 views, stage stepper, and UI primitives
│   │   ├── types/               # TypeScript interfaces mirroring all 12 backend schemas
│   │   ├── views/               # 10 platform views
│   │   ├── App.tsx              # Root app component
│   │   └── main.tsx
│   ├── package.json
│   └── tailwind.config.js       # Dark navy tokens + severity palette (low/medium/high/critical)
├── docs/                        # Architecture documentation & method notes
├── .gitignore
└── README.md
```

---

## 📐 Core Architecture Rules

1. **Provider Interfaces (`backend/app/providers/base.py`)**:
   - `ASRProvider`: Word/segment timestamped transcription. Primary: Mistral Voxtral; local fallback: `faster-whisper`.
   - `LLMProvider`: Structured JSON output validated by Pydantic. Supports `mistral-large-latest` (default) and `gemini-3.5-flash-lite` (optional adapter).
   - `EmbeddingProvider`: Vector embeddings (`mistral-embed` / `gemini-embedding-001`) with persistent ChromaDB storage partitioned by provider, model, and dimension.
2. **Deterministic 3D Coordinates $(x, y, z)$**:
   - Every domain entity carries pedagogical coordinates for Three.js spatial graph visualization:
     - $x$: Time position normalized to $[0.0, 100.0]$
     - $y$: Confusion score normalized to $[0.0, 100.0]$
     - $z$: Topic hierarchy depth $[0.0, 10.0]$
3. **Structured JSON Mode & Retry-Once Recovery**:
   - All LLM outputs enforce Pydantic validation. On schema error, the LLM retries once with the specific validation error; if it fails again, the job terminates cleanly with an explicit error envelope. Never persist synthetic content or hardcoded fallbacks.
4. **Persisted Background Jobs & One-Click Pipeline**:
   - Long-running tasks execute asynchronously with persisted progress percentages and status (`queued`, `running`, `failed`, `done`). `POST /api/v1/lectures/{id}/analyze` orchestrates all 8 stages with granular progress and clean failure resumption.
5. **10 Platform Views & Zero Fake Fallbacks**:
   - `landing`, `dashboard`, `library`, `upload`, `analysis`, `evidence`, `misconceptions`, `student`, `reports`, `settings`. All views consume live REST APIs. The Demo Mode indicator in the header provides a visual presenter toggle without injecting mock content.


---

## ⚡ Quick Start: Windows PowerShell

### 1. Prerequisites
- **Python 3.11+** installed and available in PATH.
- **Node.js 18+ / 24+** and **npm** installed.
- **ffmpeg** installed (required for audio extraction).

---

### 2. Backend Setup & Run

Open a Windows PowerShell terminal in the repository root:

```powershell
# Navigate to the backend directory
cd backend

# Create and activate virtual environment (optional but recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r requirements.txt

# Configure environment variables
# Copy .env.example if .env does not exist:
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# Run database migrations
python -m alembic upgrade head

# Start the FastAPI backend server with hot reload
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend API will be running at:
- **API Base**: `http://127.0.0.1:8000/api/v1`
- **Health Check**: `http://127.0.0.1:8000/api/v1/health`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`

---

### 3. Running Backend Tests

In PowerShell from the `backend/` directory:

```powershell
# Run all pytest test suites
python -m pytest -v
```

All 96 backend tests across 18 test modules will execute, covering:
- Health, resilience, and error envelope endpoints
- Media ingestion (streaming upload limits, `yt-dlp` YouTube downloads, `ffmpeg` 16kHz mono WAV extraction, ffprobe validation)
- Transcription pipeline (faster-whisper and cloud ASR with word timestamps and 5-minute chunk overlap de-duplication)
- Empirical confusion signal engine (`docs/CONFUSION_METHOD.md`), 30-60s sliding windows, and hierarchical topic segmentation
- Structured LLM extraction of potential misconceptions (inferred from lecture speech) with model confidence and cognitive load scoring & bounded concurrency
- ChromaDB persistent vector retrieval isolated per provider+model+dimension and prerequisite graph tracing
- Teacher interventions synthesis (recap checklists, analogies, diagnostic checks)
- Student catch-up package synthesis & grounded Socratic AI tutor
- Pedagogy quality audit reports, quantitative metrics, and multi-format exports
- Schema migration via Alembic covering all 12 entities with SQLite WAL & busy_timeout
- Unified one-click 8-stage pipeline (`/analyze`) with stage provenance and provider-mismatch resume invalidation

---

### 4. Frontend Setup & Run

Open a second Windows PowerShell terminal in the repository root:

```powershell
# Add Node.js to PATH if necessary
$env:PATH = "C:\Program Files\nodejs;$env:APPDATA\npm;$env:PATH"

# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```

Frontend will be running at:
- **Local Dev Server**: `http://localhost:5173/`

---

### 5. Running Frontend Tests & Production Build

In PowerShell from the `frontend/` directory:

```powershell
# Run all 49 Vitest tests across 15 test suites covering 10 views, stage stepper, analyze flow, and UI primitives
npm test -- --run

# Run strict TypeScript check and build production bundle
npm run build
```


---

## 🧪 Severity Palette & UI Tokens

The frontend uses a custom Dark-Navy SaaS palette with 4 distinct severity tiers:

| Severity Level | Border / Text Accent | Usage |
|---|---|---|
| `low` | Emerald (`#10b981`) | Normal comprehension, healthy pacing, resolved gaps |
| `medium` | Cyan (`#06b6d4`) | Informational, moderate friction, baseline metrics |
| `high` | Amber (`#f59e0b`) | Warning, elevated hesitation, potential confusion cluster |
| `critical` | Rose (`#f43f5e`) | High cognitive bottleneck, misconception detected |

---

## 🛡️ License
MIT License - Created for ClassSense.
#   C l a s s - S e n s e  
 