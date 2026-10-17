# ClassSense Confusion Detection Methodology & Formulations

## 1. Overview
ClassSense combines acoustic/temporal speech analysis, linguistic hesitation detection, and large language model (LLM) cognitive load scoring to detect moments where students are likely to experience cognitive friction, instructional pacing issues, or misconceptions during lectures.

Every confusion point computed in ClassSense relies on deterministic acoustic and lexical formulas computed over **30–60 second sliding windows**, combined with Pydantic-validated structured LLM reasoning and **strict exact substring quote validation**. No hardcoded or mock scores are used in the analysis pipeline.

---

## 2. Sliding Window Architecture (30–60s)
Rather than evaluating arbitrary ASR transcript segments (which range from 1 to 20 seconds depending on speech pauses), ClassSense constructs sliding temporal windows across the lecture:
- **Window Length ($W$)**: Default $45.0\text{ seconds}$ (configurable between $30.0$ and $60.0\text{s}$).
- **Step Size ($\Delta t$)**: Default $15.0\text{ seconds}$ ($66\%$ overlap between consecutive windows).
- **Window Coverage**: If the total duration $T \le W$, a single window $[0, T]$ covers the entire recording.

Each window collects all word timestamps and transcript tokens falling within $[t_{\text{win\_start}}, t_{\text{win\_end}}]$.

---

## 3. The 6 Acoustic & Linguistic Signals

### 3.1 Speech Rate Anomaly ($z_{\text{WPM}}$)
Instructors explaining challenging concepts frequently exhibit either sudden deceleration (hesitant, deliberate searching for terms) or rapid acceleration (rushing through difficult material).

Given a window with word count $N_w$ and duration $\Delta t = t_{\text{end}} - t_{\text{start}}$:
$$\text{WPM} = \frac{N_w}{\Delta t / 60.0}$$

The speech rate anomaly $z_{\text{WPM}}$ is computed relative to the baseline lecture mean $\mu_{\text{WPM}}$ and standard deviation $\sigma_{\text{WPM}}$:
$$z_{\text{WPM}} = \frac{|\text{WPM} - \mu_{\text{WPM}}|}{\sigma_{\text{WPM}} + \epsilon}$$
Normalized signal:
$$S_{\text{wpm}} = \min\left(1.0, \frac{z_{\text{WPM}}}{2.5}\right)$$

### 3.2 Pause and Silence Density ($D_{\text{pause}}$)
Intra-window silence ratio indicates cognitive hesitation or difficulty formulating concepts. For adjacent word boundaries $(w_i, w_{i+1})$ with timestamps $(t_{i,\text{end}}, t_{i+1,\text{start}})$:
$$\text{PauseTime} = \sum_{i=1}^{N_w - 1} \mathbf{1}_{\{t_{i+1,\text{start}} - t_{i,\text{end}} \ge 0.20\}} \cdot (t_{i+1,\text{start}} - t_{i,\text{end}})$$
$$D_{\text{pause}} = \frac{\text{PauseTime}}{\Delta t}$$
Normalized signal:
$$S_{\text{pause}} = \min(1.0, D_{\text{pause}} \times 2.5)$$

### 3.3 Disfluency Ratio ($R_{\text{disfluency}}$)
Measures acoustic filler tokens (e.g., "um", "uh", "er", "ah", "erm", "hmm", "like", "you know", "sort of", "kind of"):
$$R_{\text{disfluency}} = \frac{N_{\text{fillers}}}{N_w}$$
Normalized signal:
$$S_{\text{disfluency}} = \min(1.0, R_{\text{disfluency}} \times 4.0)$$

### 3.4 Repetition Ratio ($R_{\text{repetition}}$)
Measures immediate lexical backtracking and stutters (e.g., "if if", "we we consider"):
$$R_{\text{repetition}} = \frac{N_{\text{repetitions}}}{N_w}$$
Normalized signal:
$$S_{\text{repetition}} = \min(1.0, R_{\text{repetition}} \times 4.0)$$

### 3.5 Question Density ($D_{\text{question}}$)
High concentrations of concept-check questions from instructors or clarifying questions from students indicate points of active comprehension strain:
$$Q_{\text{rate}} = \frac{N_{\text{questions}}}{\max(0.2, \Delta t / 60.0)}$$
Normalized to $[0, 1]$ where $\ge 3$ questions/minute yields $1.0$:
$$S_{\text{question}} = \min\left(1.0, \frac{Q_{\text{rate}}}{3.0}\right)$$

### 3.6 Student Response Gap ($G_{\text{response}}$)
Measures post-question silence or latency. When an instructor asks a question, an extended silence before a response indicates student hesitation, lack of confidence, or conceptual stumbling:
$$G_{\text{max}} = \max_{i \in \text{Questions}} (t_{\text{next\_speech}} - t_{\text{question\_end}})$$
Normalized where a silence $\ge 4.0\text{s}$ yields $1.0$:
$$S_{\text{gap}} = \min\left(1.0, \frac{G_{\text{max}}}{4.0}\right)$$

---

## 4. Multi-Signal Composite Score ($S_{\text{signal}}$)
The 6 normalized signals are combined using configurable linear weights:
$$S_{\text{signal}} = w_{\text{pause}} S_{\text{pause}} + w_{\text{wpm}} S_{\text{wpm}} + w_{\text{disfl}} S_{\text{disfluency}} + w_{\text{rep}} S_{\text{repetition}} + w_{\text{q}} S_{\text{question}} + w_{\text{gap}} S_{\text{gap}}$$

Default weights:
- $w_{\text{pause}} = 0.20$
- $w_{\text{wpm}} = 0.20$
- $w_{\text{disfl}} = 0.15$
- $w_{\text{rep}} = 0.15$
- $w_{\text{q}} = 0.15$
- $w_{\text{gap}} = 0.15$

A window is **flagged** for LLM evaluation if $S_{\text{signal}} \ge 0.28$ or if any individual signal exceeds its spike threshold.

---

## 5. LLM Cognitive Evaluation & Exact Substring Quote Validation

### 5.1 LLM Structured Pass
Every flagged window undergoes an LLM pass in structured JSON mode using `LLMWindowConfusionAnalysis`:
- `confusion_score`: float $\in [0.0, 1.0]$
- `ai_confidence`: float $\in [0.0, 1.0]$
- `evidence_quote`: exact verbatim substring from the window transcript
- `rationale`: pedagogical explanation of the cognitive difficulty or misconception

### 5.2 Shortest Verbatim Evidence Excerpt & Validation Contract
To prevent hallucinated or overly verbose evidence, the validator enforces that `evidence_quote` is BOTH the shortest verbatim excerpt supporting the score (maximum 30 words, 1–2 sentences) AND an exact substring of the window transcript:
$$\text{evidence\_quote} \subseteq \text{window\_transcript} \quad \land \quad \text{len}(\text{words}(\text{evidence\_quote})) \le 30$$
1. If valid: the evaluation is accepted.
2. If invalid (either not an exact substring or exceeding 30 words): ClassSense logs a warning and **retries the LLM call once** with an explicit directive requiring character-for-character extraction within the 30-word limit.
3. If the retry fails validation: ClassSense **drops the confusion event** and logs the specific reason (exact mismatch or length breach). It never persists fabricated or unverified quotes.

---

## 6. Score Fusion Formula ($C_{\text{final}}$)
The final confusion score fuses the acoustic/linguistic signal score with the LLM cognitive evaluation:
$$C_{\text{final}} = w_{\text{signal}} \cdot S_{\text{signal}} + w_{\text{llm}} \cdot S_{\text{LLM}}$$
Configurable weights (defaults: $w_{\text{signal}} = 0.40$, $w_{\text{llm}} = 0.60$).

---

## 7. Deterministic 3D Coordinate Projection
Every confusion event and evidence item is projected into 3D Cartesian coordinates $(x, y, z)$:
- **$x$ (Time Axis)**: Temporal percentage through the lecture:
  $$x = \left(\frac{t_{\text{start}}}{T_{\text{total}}}\right) \times 100.0$$
- **$y$ (Confusion Intensity)**: Final fused confusion score:
  $$y = C_{\text{final}} \times 100.0$$
- **$z$ (Pedagogical Topic Depth)**: Hierarchical depth in the outline:
  $$z = \text{depth} \times 1.0$$

---

## 8. Honest Limitations & Assumptions
1. **Single-Track Audio Diarization**: When recording from a single room microphone, acoustic separation between instructor and students relies on energy levels and pause gaps. Overlapping speech without dedicated multi-channel inputs can slightly distort silence gap measurements.
2. **Pedagogical Wait-Time Intent**: Instructors practicing effective Socratic wait-time deliberately introduce 3–5s pauses after questions. While often correlated with deep thinking or difficulty, intentional wait-time is distinguished from confusion by the LLM semantic pass.
3. **ASR Timestamp Precision**: Word-level timestamps from Faster-Whisper or Voxtral have $\approx 100\text{–}200\text{ms}$ jitter at word boundaries in noisy classrooms. Pause detection filters ignore gaps $< 200\text{ms}$ to avoid false positives.
4. **Cultural and Speaking Style Variations**: Natural speech cadence varies across instructors. Computing dynamic lecture-level baselines ($\mu_{\text{WPM}}, \sigma_{\text{WPM}}$) normalizes for individual baseline differences but cannot fully normalize sudden stylistic transitions (e.g. reading from prepared slides vs spontaneous answering).
5. **Zero Confusion as a Valid Outcome**: A calm, well-articulated lecture may yield zero confusion events when all fused scores remain below `CONFUSION_MIN_SCORE` (default $0.35$). Downstream stages handle this outcome gracefully without synthesizing hallucinations.

---

## 9. Report Calibration, Pacing Bands & Factual Guardrails

### 9.1 Deterministic Speech Rate & Pacing Bands
Lecture delivery pacing is computed deterministically from transcript segments and duration:
$$\text{WPM} = \frac{\sum_{s \in \text{Segments}} \text{words}(s)}{\max(0.1, T_{\text{speaking\_minutes}})}$$

Pacing is deterministically mapped to configurable bands (`WPM_BAND_SLOW_MAX = 110.0`, `WPM_BAND_FAST_MIN = 180.0`):
- **Slow**: $\text{WPM} < 110$ (hesitant or heavily deliberate pacing)
- **Normal**: $110 \le \text{WPM} \le 180$ (standard collegiate lecturing cadence; e.g., $163\text{ WPM}$ is normal)
- **Fast**: $\text{WPM} > 180$ (rapid delivery, heightened risk of cognitive overload)

### 9.2 Deterministic Pause Metrics & Density
Pauses are deterministically computed by examining intra-segment and inter-segment gaps $\ge 1.5\text{ seconds}$:
$$D_{\text{pause}} = \frac{T_{\text{pause\_seconds}}}{\max(1.0, T_{\text{total}})}$$
- **Low**: $D_{\text{pause}} < 10\%$ (continuous flow)
- **Moderate**: $10\% \le D_{\text{pause}} \le 25\%$ (standard instructional pauses)
- **High**: $D_{\text{pause}} > 25\%$ (frequent hesitation gaps)

### 9.3 LLM Prompt Factual Integrity Guardrails
The report generation prompt explicitly passes the empirical WPM, pause metrics, and assigned band labels to the LLM. The system prompt strictly enforces that the LLM must **never fabricate pacing claims that contradict the metrics**:
- Normal-band delivery ($110\text{–}180\text{ WPM}$, e.g. $163\text{ WPM}$) must **never** be characterized as fast, rushed, rapid, or accelerated.
- Normal-band delivery must **never** be characterized as slow, sluggish, or dragging.
- All executive summary narratives and key recommendations must ground their qualitative insights strictly within the empirical boundaries of the provided data.

---

## 10. Honest Epistemic Framing: Potential Misconceptions (Inferred from Lecture Speech)

### 10.1 Epistemic Modesty
ClassSense uses the terminology **"Potential misconceptions (inferred from lecture speech)"** throughout all user interfaces, API descriptions, and reports, deliberately avoiding overconfident or clinical phrasing such as "diagnosed misconceptions".

Because the analysis is grounded in instructor speech signals (hesitation pauses, disfluency bursts, acoustic stalls, and verbal quotes) rather than direct psychometric student testing or EEG telemetry, these represent **pedagogical hypotheses** of mental model breakdown points.

### 10.2 Transparent Model Confidence
Every potential misconception item presents:
- **Model Confidence**: The calibrated confidence level ($0.0\text{–}1.0$) returned by the structured reasoning pass, reflecting the strength of evidence in the spoken window.
- **Cognitive Load Score**: The estimated intensity of mental model friction.
- **Pedagogical Severity**: Categorized as `low`, `medium`, `high`, or `critical`.
- **Root Prerequisite Gap**: The traced foundational concept from the prerequisite knowledge graph.


