# ClassSense — Professor Demonstration Guide & Viva Cheat Sheet

**Project Title**: ClassSense: Multi-Signal Cognitive Friction & Autonomous Pedagogical Knowledge Graph Engine  
**Live URL**: `http://127.0.0.1:8000/` (Zero-Build Live Dashboard) & `http://127.0.0.1:8000/docs` (Interactive OpenAPI Swagger UI)  
**One-Click Demo Command**: Run `start_demo.bat` in the project root, or `python run_demo.py` in `backend/`.

---

## 1. Executive Summary & Problem Formulation

### The Problem
During college STEM lectures, instructors cannot observe real-time student cognitive strain. Traditional feedback mechanisms (clickers, surveys, or post-exam postmortems) are post-hoc, coarse-grained, and disruptive to natural lecture flow.

### The ClassSense Innovation
ClassSense is an end-to-end pedagogical AI system that:
1. **Listens to Lecture Delivery**: Analyzes temporal acoustics and lexical cadence over **30–60 second sliding windows** with $66\%$ overlap.
2. **Extracts 6 Empirical Hesitation Signals**:
   - $z_{\text{WPM}}$: Sudden speech acceleration or deceleration anomaly.
   - $D_{\text{pause}}$: Inter-word silence density ($\ge 200\text{ms}$).
   - $R_{\text{disfluency}}$: Acoustic filler tokens ("um", "uh", "you know").
   - $R_{\text{repetition}}$: Lexical stutters and backtracking.
   - $D_{\text{question}}$: Checkpoint question density per minute.
   - $G_{\text{response}}$: Post-question latency and extended silence.
3. **Fuses Signals with Validated LLM Scoring**: Combines deterministic signal z-scores with schema-constrained LLM cognitive evaluations and **shortest exact substring evidence quotes** ($\le 30$ words).
4. **Traces Prerequisite Knowledge Graphs**: Connects flagged struggle points backwards into missing foundational concepts using ChromaDB vector search.
5. **Generates Dual Interventions**:
   - **For Teachers**: 3-minute next-lecture opening recaps, in-class diagnostic check questions, and blackboard physical analogies.
   - **For Students**: Self-paced catch-up modules, real-world analogies, and Socratic checkpoint quizzes with progressive multi-step hints.
6. **Live Socratic Conversational AI Tutor**: A grounded, conversational tutor answering student questions using lecture transcripts and prerequisite anchors.

---

## 2. 12-Entity Database Architecture

ClassSense operates on a normalized SQLite schema with **Write-Ahead Logging (WAL)** and automated migrations via **Alembic** (`e170a277b191_initial_schema_all_12_entities.py`):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ClassSense Data Model                            │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ 1. lectures          │ Core recording unit  │ id, title, media/audio_path,  │
│                      │                      │ duration, status, 3D coords   │
│ 2. transcript_segs   │ Word-level ASR text  │ lecture_id, start/end, words  │
│ 3. topics            │ Hierarchy outline    │ lecture_id, parent_id, depth  │
│ 4. confusion_events  │ Empirical friction   │ lecture_id, score, signals,   │
│                      │ points               │ evidence_text, timestamps     │
│ 5. evidence          │ Verbatim excerpts    │ confusion_id, quote, type,    │
│                      │                      │ confidence, timestamps        │
│ 6. misconceptions    │ Potential mental     │ confusion_id, name, reason,   │
│                      │ model breakdowns     │ severity, cognitive_load      │
│ 7. prereq_nodes      │ ChromaDB graph nodes │ confusion_id, concept_name,   │
│                      │                      │ depth (1-3), vector_dist      │
│ 8. interventions     │ Teacher cockpit      │ lecture_id, target_type,      │
│                      │                      │ content (recap, analogies, dq)│
│ 9. student_catchups  │ Student remediation  │ lecture_id, topic_id, analogy,│
│                      │                      │ summary, key_takeaways        │
│ 10. quiz_questions   │ Self-check quizzes   │ catchup_id, question, options,│
│                      │                      │ progressive hints (steps 1-3) │
│ 11. reports          │ Pedagogy quality KPI │ lecture_id, metrics, narrative│
│                      │                      │ recommendations, export_fmt   │
│ 12. jobs             │ Async job pipeline   │ job_type, status, progress_pct│
│                      │ orchestrator         │ payload, error, result        │
└──────────────────────┴──────────────────────┴───────────────────────────────┘
```

---

## 3. Multi-Provider Resilience & Event Loop Architecture

### Multi-Provider Fallback Matrix
- **Speech-to-Text (ASR)**: Local `Faster-Whisper` (no API key required, zero external dependencies) $\rightarrow$ Mistral Voxtral $\rightarrow$ Gemini Audio.
- **Cognitive Reasoning (LLM)**: Google Gemini (`gemini-3.5-flash-lite` via `google-genai` SDK) $\leftrightarrow$ Mistral AI (`mistral-large-latest`).
- **Vector Embeddings**: ChromaDB persistent vector store isolated by provider, model, and dimension (`prerequisite_kb_gemini_3072` vs `prerequisite_kb_mistral_1024`).

### Resilience Mechanics
1. **Async Non-Blocking Execution**: Synchronous provider calls (`client.models.generate_content`, `WhisperModel.transcribe`) are offloaded via `asyncio.to_thread` or native async coroutines, keeping FastAPI’s health probes responding in $< 500\text{ms}$.
2. **Global Concurrency Semaphore**: Limits simultaneous external API calls to `PROVIDER_MAX_CONCURRENCY = 3` to prevent rate-limit throttling.
3. **Exponential Backoff with Jitter**: Automatically retries transient HTTP 429 / 503 and timeouts up to 3 attempts with random jitter.
4. **Stuck Job Self-Healing**: On server restart, `lifespan` automatically sweeps `running` or `queued` jobs and marks them as interrupted, allowing seamless `POST /analyze?resume=true`.

---

## 4. The 3-Minute Live Demonstration Script (Step-by-Step)

### Minute 0:00 – 0:45: The System Overview & Live Dashboard
1. Open `http://127.0.0.1:8000/`.
2. **Say to Professor**:
   > *"Professor, this is ClassSense. It is an autonomous cognitive friction and pedagogical quality auditor. Instead of relying on post-exam surveys, it parses the instructor's spoken speech, extracts empirical hesitation anomalies over 30-60s sliding windows, maps student misconceptions into prerequisite vector graphs, and synthesizes actionable teaching interventions."*
3. Point out the **top status bar**:
   - Show the green pulse indicator (`FastAPI Engine Online`).
   - Show the ChromaDB Vector Graph indicator.
   - Click the **"Load Calculus Demo"** button. The dashboard instantly renders the complete 8-stage analysis with zero latency.

---

### Minute 0:45 – 1:30: Topics, Sliding Window Signals & Evidence
1. Click **"Topics & Transcript"** (Tab 1):
   - Show the 3 segmented topics and the word-aligned transcript with timestamps.
2. Click **"Cognitive Friction Signals"** (Tab 2):
   - **Say to Professor**:
     > *"Here are the empirical signals. The system detected a friction spike at minute 0:46 with a score of 76%. Notice the breakdown: pause density of 38%, speech rate anomaly of 2.1 sigma, and the verbatim excerpt quote: 'Now wait... notice how the gradient points perpendicular to the contour lines?'. Every quote is strictly validated as an exact substring of the spoken window."*

---

### Minute 1:30 – 2:15: Potential Misconceptions, Honest Framing & ChromaDB Prerequisites
1. Click **"Potential Misconceptions & Prerequisites"** (Tab 3):
   - **Say to Professor**:
     > *"Notice the honest epistemic framing: 'Potential misconceptions (inferred from lecture speech)'. Because we analyze speech friction rather than direct brain scans, we frame them as pedagogical hypotheses. Each misconception displays the model's calibrated confidence—here, 89% confidence—alongside cognitive load."*
2. Point out the **Traced Upstream Prerequisites**:
   - Show Depth 1 (`Partial Derivatives`, vector distance 0.182), Depth 2 (`Single-Variable Chain Rule`, 0.245), and Depth 3 (`Dot Product & Cauchy-Schwarz`, 0.312).
   - Explain: *"These foundational gaps were retrieved from ChromaDB vector space based on semantic proximity to the flawed intuition."*

---

### Minute 2:15 – 3:00: Teacher Cockpit, Socratic Tutor & Executive Report
1. Click **"Teacher Interventions"** (Tab 4):
   - Show the **3-Minute Opening Recap** and the **Blackboard Analogy** (*"The Foggy Mountain Hiker"*).
2. Click **"Student Catch-Up & Socratic Tutor"** (Tab 5):
   - Expand the **Self-Check Checkpoint Quiz**. Click **"Hint 1"**, then **"Hint 2"**, then **"Hint 3"** to demonstrate the progressive Socratic scaffolding.
   - On the right side, type in the live chat box:
     `"Why does the gradient vector point orthogonal to the contour curve?"`
   - Click **Send** and watch the live Socratic tutor formulate a guided inquiry response grounded in the lecture!
3. Click **"Pedagogy Audit Report"** (Tab 6):
   - Highlight the **KPI summary grid**: Confusion density (18%), Delivery pacing (134 WPM mapped to the *Normal Pacing Band*), and click **"Export Markdown"** to show instant exportability.

---

## 5. Potential Professor Questions & High-Scoring Answers

### Q1: *"Why do you use sliding windows instead of analyzing sentence by sentence?"*
**Answer**:
> *"Sentence-level ASR segments vary wildly from 1 to 20 seconds depending on speech pauses, which skews rate-of-speech statistics. By using 45-second sliding windows with 15-second steps (66% overlap), we ensure a statistically stable duration to compute Words Per Minute (WPM), pause density ratios, and disfluency rates, while ensuring that acoustic hesitation spanning segment boundaries is never missed."*

### Q2: *"What happens if a lecture is delivered smoothly and there are no confusion points?"*
**Answer**:
> *"Zero events is a valid pedagogical outcome. We enforced a configurable gate `CONFUSION_MIN_SCORE = 0.35`. If all fused scores remain below 0.35, the pipeline cleanly completes downstream stages without inventing hallucinations. The UI renders an explicit 'High Instructional Clarity' outcome instead of generating fake errors."*

### Q3: *"How do you prevent the LLM from hallucinating quotes or evidence?"*
**Answer**:
> *"We implemented strict deterministic quote validation (`validate_quote_substring`). Every evidence quote returned by the model must satisfy two criteria: it must be an exact substring of that window's transcript text, and it must be at most 30 words (1-2 sentences). If either check fails, the system automatically retries once with explicit error feedback; if it fails again, the event is cleanly dropped with a logged reason."*

### Q4: *"How do you ensure the server doesn't freeze or lock up with SQLite under concurrent requests?"*
**Answer**:
> *"We enabled SQLite Write-Ahead Logging (WAL) mode with `PRAGMA journal_mode=WAL` and a 30-second `busy_timeout`. Furthermore, all long-running LLM and ChromaDB queries execute in non-blocking threads with an immediate `db.commit()` before launching asynchronous background tasks, preventing database lock contention."*
