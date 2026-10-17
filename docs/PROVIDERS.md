# AI Providers & Adapter Architecture

ClassSense decouples domain business logic from third-party AI APIs through abstract provider interfaces (`ASRProvider`, `LLMProvider`, `EmbeddingProvider`).

---

## 1. Primary AI Stack (Default)

Per the project specification, **Mistral AI** is the primary cloud AI provider and **faster-whisper** is the local speech-to-text fallback:

| Capability | Provider | Model ID | Config Variable | Notes |
|---|---|---|---|---|
| **LLM (JSON Mode)** | Mistral | `mistral-large-latest` | `LLM_PROVIDER="mistral"` | Strict JSON mode with Pydantic validation and retry-once recovery. |
| **Embeddings** | Mistral | `mistral-embed` | `EMBEDDING_PROVIDER="mistral"` | Generates dense vectors for prerequisite knowledge graph in ChromaDB. |
| **ASR (Cloud)** | Mistral | `voxtral-mini-latest` | `ASR_PROVIDER="mistral_voxtral"` | Word-level timestamps via official `mistralai` SDK. |
| **ASR (Local Fallback)** | faster-whisper | `base` (CPU / int8) | `ASR_PROVIDER="faster_whisper"` | Runs fully offline without external API dependency. |

---

## 2. Optional Adapter: Google Gemini

An optional **Google Gemini** adapter is available when a Gemini API key is configured. It is enabled via configuration:

```ini
# backend/.env
LLM_PROVIDER="gemini"
EMBEDDING_PROVIDER="gemini"
ASR_PROVIDER="gemini_audio"   # Or "faster_whisper"
GEMINI_API_KEY="your-gemini-key"
```

| Capability | Adapter Class | Default Model ID | Notes |
|---|---|---|---|
| **LLM** | `GeminiLLMProvider` | `gemini-3.5-flash-lite` | Strict JSON schema structured mode with retry-once recovery. |
| **Embeddings** | `GeminiEmbeddingProvider` | `gemini-embedding-001` | Produces dense embeddings stored in dynamic collections by provider+model+dimension in ChromaDB. |
| **ASR** | `GeminiAudioASR` | `gemini-3.5-flash-lite` | Multimodal audio transcription returning segment and word timestamps. |


---

## 3. Unimplemented Adapters

- **OpenAI Whisper (`openai_whisper`)**: Adapter stub; raises `ADAPTER_NOT_IMPLEMENTED` (HTTP 501) on registration or selection.
- **Sarvam AI (`sarvam_ai`)**: Adapter stub; raises `ADAPTER_NOT_IMPLEMENTED` (HTTP 501) on registration or selection.

---

## 4. Switching Providers

Providers are selected via environment variables in `backend/.env`:

```ini
# Default Configuration (Mistral + faster-whisper)
LLM_PROVIDER="mistral"
EMBEDDING_PROVIDER="mistral"
ASR_PROVIDER="faster_whisper"
MISTRAL_API_KEY="your_actual_mistral_api_key_here"

# Alternative Configuration (Gemini)
LLM_PROVIDER="gemini"
EMBEDDING_PROVIDER="gemini"
ASR_PROVIDER="faster_whisper"
GEMINI_API_KEY="your_gemini_api_key_here"
```
