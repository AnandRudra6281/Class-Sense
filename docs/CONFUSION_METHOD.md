# ClassSense Confusion Detection Methodology & Formulations

## 1. Overview
ClassSense combines acoustic/temporal speech analysis, linguistic hesitation detection, and large language model (LLM) cognitive load scoring to detect moments where students are likely to experience cognitive friction or misconceptions during lectures.

Every confusion point computed in ClassSense relies on deterministic acoustic and lexical formulas combined with Pydantic-validated structured LLM reasoning. No hardcoded or mock scores are used in the analysis pipeline.

---

## 2. Core Acoustic & Temporal Formulas

### 2.1 Speech Rate Anomalies ($\Delta_{\text{WPM}}$)
When instructors explain difficult concepts, speech rate often exhibits either sudden deceleration (hesitant, deliberate searching for terms) or rapid acceleration (rushing through difficult prerequisites).

Given a segment $s$ spanning $[t_{\text{start}}, t_{\text{end}}]$ with word count $N_w$:
$$\text{WPM}(s) = \frac{N_w}{(t_{\text{end}} - t_{\text{start}}) / 60}$$

The speech rate anomaly $z_{\text{WPM}}(s)$ is computed relative to the baseline lecture mean $\mu_{\text{WPM}}$ and standard deviation $\sigma_{\text{WPM}}$:
$$z_{\text{WPM}}(s) = \frac{|\text{WPM}(s) - \mu_{\text{WPM}}|}{\sigma_{\text{WPM}} + \epsilon}$$

### 2.2 Pause and Silence Density ($D_{\text{pause}}$)
Intra-segment silence ratio indicates cognitive processing or difficulty formulating concepts. For word boundaries $(w_i, w_{i+1})$ with timestamps $(t_{i,\text{end}}, t_{i+1,\text{start}})$:
$$\text{PauseTime}(s) = \sum_{i=1}^{N_w - 1} \max\left(0, t_{i+1,\text{start}} - t_{i,\text{end}}\right)$$
$$D_{\text{pause}}(s) = \frac{\text{PauseTime}(s)}{t_{\text{end}} - t_{\text{start}}}$$

### 2.3 Disfluency and Repetition Ratio ($R_{\text{disfluency}}$)
Disfluencies include acoustic filler tokens (e.g., "um", "uh", "err") and lexical backtrack repetitions (e.g., "if we... if we look at..."):
$$R_{\text{disfluency}}(s) = \frac{N_{\text{fillers}} + N_{\text{repetitions}}}{N_w + \epsilon}$$

---

## 3. Linguistic & Lexical Complexity

### 3.1 Type-Token Ratio & Lexical Density
Measures lexical variety and concept compactness:
$$\text{TTR}(s) = \frac{|V(s)|}{N_w}$$
where $|V(s)|$ is the number of unique word stems in segment $s$.

---

## 4. Multi-Signal Composite Confusion Score ($C_{\text{composite}}$)

The acoustic/temporal composite signal $S_{\text{acoustic}}(s) \in [0, 1]$ is:
$$S_{\text{acoustic}}(s) = \sigma\left(w_1 \cdot z_{\text{WPM}}(s) + w_2 \cdot D_{\text{pause}}(s) + w_3 \cdot R_{\text{disfluency}}(s) - \theta\right)$$
where default weights are $w_1 = 0.30$, $w_2 = 0.40$, $w_3 = 0.30$, and $\theta$ is an empirical calibration bias.

The final confusion score $C(s) \in [0, 1]$ fuses $S_{\text{acoustic}}(s)$ with LLM-evaluated cognitive friction $S_{\text{LLM}}(s)$:
$$C(s) = \alpha \cdot S_{\text{acoustic}}(s) + (1 - \alpha) \cdot S_{\text{LLM}}(s)$$
with default weighting $\alpha = 0.35$.

---

## 5. Deterministic 3D Coordinate Mapping
Every topic and confusion point is projected into 3D Cartesian coordinates $(x, y, z)$ for visualization:
- **$x$ (Time Axis)**: Normalized temporal position in the lecture:
  $$x = \left(\frac{t_{\text{start}}}{T_{\text{total}}}\right) \times 100.0$$
- **$y$ (Confusion Intensity)**: Composite difficulty/confusion score:
  $$y = C(s) \times 100.0$$
- **$z$ (Pedagogical Depth)**: Depth in the topic hierarchy (e.g., 0 for root topic, 1 for subtopic, 2 for nested concept):
  $$z = \text{depth} \times 1.0$$

---

## 6. Limitations & Assumptions
1. **Microphone & Recording Quality**: High background noise or poor acoustics can skew word boundary timestamp accuracy and artificially elevate pause ratios.
2. **Instructor Idiosyncrasies**: Some speakers naturally speak with rapid cadence or long pauses regardless of concept difficulty; baseline normalization across the entire recording mitigates but does not completely eliminate this bias.
3. **Pacing vs. Struggle**: Intentional dramatic pauses or Socratic pauses before asking student questions must be differentiated from cognitive hesitation by combining acoustic signals with transcript semantic analysis.
4. **Multimodal Information**: ClassSense currently evaluates speech audio and transcripts; physical gestures, whiteboard handwriting, and student facial expressions (if video) are not yet in the acoustic signal path.
