# ClassSense: Intelligent Pedagogy & Cognitive Friction Platform

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6+-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4+-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4+-06B6D4?style=flat&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![SQLite](https://img.shields.io/badge/SQLite-WAL_Mode-003B57?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Tests: Pytest](https://img.shields.io/badge/Pytest-108%20Passed-4B8BBE?style=flat&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Tests: Vitest](https://img.shields.io/badge/Vitest-49%20Passed-FCC72B?style=flat&logo=vitest&logoColor=black)](https://vitest.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **ClassSense** is an AI teaching assistant and automated pedagogical intelligence platform. It analyzes lecture audio/video to detect where students experience cognitive friction, isolates root prerequisite misconceptions using vector retrieval across persistent ChromaDB embeddings, equips instructors with actionable blackboard interventions, and provides students with an interactive Socratic remediation guide.

---

## 🏛️ System Architecture

ClassSense is engineered as a production-grade monorepo combining an asynchronous FastAPI backend and a high-performance React + TypeScript SPA.

```
Class-Sense/
├── backend/
│   ├── alembic/                 # Database schema migrations (Alembic)
│   ├── app/
│   │   ├── api/v1/              # RESTful API endpoints (/health, /jobs, /lectures)
│   │   ├── core/                # Configuration, error envelope, path normalization
│   │   ├── db/                  # Async SQLite session with WAL mode & foreign keys
│   │   ├── models/              # SQLAlchemy 2.x declarative models for all 12 entities
│   │   ├── providers/           # Abstract provider interfaces + Mistral & Gemini adapters
│   │   ├── schemas/             # Pydantic v2 domain schemas with 3D spatial coordinates
│   │   ├── services/            # Pipeline orchestrator, confusion engine, ASR chunker
│   │   ├── static/              # Zero-build single-file Professor Demo Dashboard
│   │   └── main.py              # FastAPI application factory with CORS & lifecycle handlers
│   ├── tests/                   # 108 async pytest tests (unit, integration, resilience)
│   ├── requirements.txt         # Pinned production dependencies
│   ├── run_demo.py              # One-click professor demonstration launcher
│   └── seed_demo_data.py        # Pre-computed Calculus & Perceptron ANN datasets
├── frontend/
│   ├── src/
│   │   ├── api/                 # Strongly-typed fetch client with standardized error envelope
│   │   ├── components/
│   │   │   ├── layout/          # AppLayout, Header, Sidebar, MobileDrawer
│   │   │   └── ui/              # Button, Card, Badge, Progress, Alert, Modal
│   │   ├── hooks/               # useNavigation (10 view IDs), useJobPolling
│   │   ├── services/            # Frontend services (jobService, lectureService)
│   │   ├── test/                # 49 Vitest tests across 15 suites
│   │   ├── types/               # TypeScript domain interfaces matching backend schemas
│   │   ├── views/               # 10 platform views (Dashboard, Evidence, Misconceptions, etc.)
│   │   ├── App.tsx              # Root router & layout component
│   │   └── main.tsx             # React DOM entry point
│   ├── package.json
│   └── tailwind.config.js       # Dark navy tokens & 4-tier severity palette
├── docs/                        # CONFUSION_METHOD.md, PROVIDERS.md
├── PROFESSOR_DEMO_GUIDE.md      # Comprehensive viva evaluation & live demo guide
├── start_demo.bat               # Windows one-click desktop batch launcher
├── .gitignore                   # Excludes secrets, databases, uploads, and node_modules
└── README.md
```

---

## 🚀 Key Platform Capabilities

1. **Empirical Cognitive Friction Engine**:
   - 30 to 60 second sliding acoustic & linguistic windows (window size = 45s, step = 15s).
   - Detects speech rate anomalies (WPM Z-score), hesitation pause density, disfluency ratios, question density, and student response latency.
   - Fuses empirical signal scores (40%) with LLM rationale (60%) under strict verbatim quote substring validation.

2. **12-Entity Relational Knowledge Graph**:
   - Every domain entity carries normalized 3D spatial coordinates (x, y, z) ready for interactive visualization:
     - **x**: Lecture timeline position normalized to [0.0, 100.0].
     - **y**: Cognitive friction / confusion score normalized to [0.0, 100.0].
     - **z**: Pedagogical topic depth [0.0, 10.0].

3. **Multi-Provider AI Resilience**:
   - **ASR**: Faster-Whisper (local 16kHz mono audio chunking with 5-minute windows and overlap de-duplication) or Mistral Voxtral / Gemini Audio.
   - **LLM**: Mistral Large (`mistral-large-latest`) or Gemini Flash Lite (`gemini-3.5-flash-lite`) with Pydantic JSON schema constraints.
   - **Embeddings & Vector Retrieval**: Persistent ChromaDB partitioned by provider, model, and vector dimension.
   - **Fault Tolerance**: Automatic fallback to local providers, exponential backoff with jitter on 429/503 errors, and bounded concurrency.

4. **One-Click 8-Stage Analysis Pipeline**:
   - `POST /api/v1/lectures/{id}/analyze` orchestrates all 8 pedagogical stages under a single tracked parent job:
     `Transcribe` ➔ `Topic Segmentation` ➔ `Confusion Analysis` ➔ `Misconceptions` ➔ `Prerequisites` ➔ `Interventions` ➔ `Student Catch-Up` ➔ `Pedagogical Audit Report`.
   - Granular per-stage progress reporting and clean failure resumption (`?resume=true`).

5. **Instructor Cockpit & Socratic Remediation**:
   - **For Teachers**: Actionable recap checklists, blackboard analogies (e.g. Foggy Mountain Hiker), and formative diagnostic questions.
   - **For Students**: Topic summaries, concrete mental models, key takeaway checklists, and progressive-hint diagnostic quizzes.

---

## ⚡ Quick Start: Windows PowerShell

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **npm**
- **FFmpeg** installed and accessible in system PATH (for audio extraction)

---

### Option A: One-Click Professor Live Demonstration (Recommended)

Run the automated runner from the project root. It applies database migrations, seeds rich Calculus & Neural Network datasets, opens your default browser, and launches the server:

```powershell
python backend/run_demo.py
```
*(Or double-click `start_demo.bat` in Windows Explorer)*

- **Interactive Professor Dashboard**: http://127.0.0.1:8000/
- **Swagger REST API Documentation**: http://127.0.0.1:8000/docs

---

### Option B: Running Full Stack (Backend + React Frontend)

#### 1. Backend Server
```powershell
# Navigate to backend and install dependencies
cd backend
pip install -r requirements.txt

# Copy environment variables
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# Apply database migrations
python -m alembic upgrade head

# Start FastAPI backend server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 2. Frontend React SPA
```powershell
# Open a second PowerShell terminal in frontend
cd frontend
npm install
npm run dev
```
- **React Application**: http://localhost:5173/

---

## 🧪 Verification & Test Suites

The project maintains 100% test coverage across both backend and frontend without any skipped or mock fallbacks:

### Backend Test Suite (108 / 108 Passing)
```powershell
# From project root
python -m pytest backend/tests -c backend/pytest.ini -v
```
Covers:
- Streaming upload safety with `MAX_UPLOAD_MB` enforcement & ffprobe validation.
- Audio extraction & 5-minute chunk overlap de-duplication with synthetic timestamp verification.
- Provider resilience, timeout handling, exponential backoff, and non-blocking event loops.
- Sliding-window confusion signal calculation, WPM banding, and exact quote validation.
- Bounded concurrency for prerequisite graph traversal and misconception extraction.
- Alembic database migration schema verification across all 12 models.
- One-click pipeline end-to-end execution and resume-on-failure verification.

### Frontend Test Suite (49 / 49 Passing)
```powershell
# From project root
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH; npm --prefix frontend test -- --run
```
Covers:
- UploadView 8-stage stepper polling, error state rendering, and retry triggers.
- Lecture service analyze flows and REST client envelope handling.
- Misconceptions view with model confidence and cognitive load indicators.
- Teacher intervention cockpit and Socratic catch-up quizzes.

### Production Build Verification
```powershell
# From project root
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH; npm --prefix frontend run build
```

---

## 🎨 UI Severity Token System

The user interface uses a dark navy theme with standardized pedagogical severity tokens:

| Level | Accent Color | Meaning |
|---|---|---|
| `low` | Emerald (`#10b981`) | Normal comprehension, healthy pacing, resolved prerequisite |
| `medium` | Cyan (`#06b6d4`) | Informational checkpoint, moderate friction, baseline metric |
| `high` | Amber (`#f59e0b`) | Warning, elevated pause hesitation, potential confusion cluster |
| `critical` | Rose (`#f43f5e`) | High cognitive bottleneck, misconception inferred from lecture speech |

---

## 🛡️ License

MIT License. Designed and engineered for ClassSense.