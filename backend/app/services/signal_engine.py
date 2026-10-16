import math
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.transcript import TranscriptSegment

FILLER_WORDS = {
    "um",
    "uh",
    "er",
    "ah",
    "erm",
    "hmm",
    "like",
    "wait",
    "you know",
    "sort of",
    "kind of",
    "actually",
}


class BaselineMetrics(BaseModel):
    mean_wpm: float = 140.0
    std_wpm: float = 25.0
    total_segments: int = 0
    total_duration: float = 0.0


class SegmentSignalMetrics(BaseModel):
    segment_id: str
    start_time: float
    end_time: float
    duration_seconds: float
    word_count: int
    wpm: float
    wpm_anomaly_z: float
    pause_time_seconds: float
    pause_density: float
    filler_count: int
    repetition_count: int
    disfluency_ratio: float
    type_token_ratio: float
    acoustic_friction_score: float
    is_confusion_spike: bool
    primary_signal: str


class SignalEngine:
    """
    Computes mathematical acoustic and lexical indicators of cognitive hesitation
    following docs/CONFUSION_METHOD.md.
    """

    def compute_lecture_baseline(self, segments: List[TranscriptSegment]) -> BaselineMetrics:
        """Computes mean WPM and standard deviation across all segments in a lecture."""
        if not segments:
            return BaselineMetrics()

        wpms: List[float] = []
        total_duration = 0.0

        for seg in segments:
            dur = max(0.1, seg.end_time - seg.start_time)
            total_duration += dur
            word_count = len(seg.words) if seg.words else len(seg.text.split())
            wpm = (word_count / dur) * 60.0
            wpms.append(wpm)

        mean_wpm = sum(wpms) / len(wpms) if wpms else 140.0
        variance = sum((w - mean_wpm) ** 2 for w in wpms) / len(wpms) if len(wpms) > 1 else 625.0
        std_wpm = max(5.0, math.sqrt(variance))

        return BaselineMetrics(
            mean_wpm=round(mean_wpm, 2),
            std_wpm=round(std_wpm, 2),
            total_segments=len(segments),
            total_duration=round(total_duration, 2),
        )

    def compute_segment_signals(
        self,
        segment: TranscriptSegment,
        baseline: BaselineMetrics,
    ) -> SegmentSignalMetrics:
        """
        Computes WPM, pause density, disfluency ratios, and acoustic friction score
        for a single transcript segment with word timestamps.
        """
        duration = max(0.1, segment.end_time - segment.start_time)
        words_data: List[Dict[str, Any]] = segment.words if segment.words else []

        # If word timestamps are missing, tokenize text
        if not words_data:
            tokens = segment.text.split()
            word_count = len(tokens)
            wpm = (word_count / duration) * 60.0
            words_data = [{"word": t, "start": segment.start_time, "end": segment.end_time} for t in tokens]
        else:
            word_count = len(words_data)
            wpm = (word_count / duration) * 60.0

        # 1. Speech Rate Anomaly Z-Score
        wpm_anomaly_z = abs(wpm - baseline.mean_wpm) / (baseline.std_wpm + 1e-5)

        # 2. Pause and Silence Density
        pause_time = 0.0
        for i in range(len(words_data) - 1):
            curr_end = float(words_data[i].get("end", 0.0))
            next_start = float(words_data[i + 1].get("start", 0.0))
            gap = next_start - curr_end
            # Pauses >= 200ms indicate hesitation/cognitive formulation
            if gap >= 0.20:
                pause_time += gap

        pause_density = min(1.0, max(0.0, pause_time / duration))

        # 3. Disfluency and Repetition Counting
        cleaned_words = [
            re.sub(r"[^\w]", "", str(w.get("word", "")).lower())
            for w in words_data
            if re.sub(r"[^\w]", "", str(w.get("word", "")).lower())
        ]

        filler_count = 0
        repetition_count = 0

        for i, word in enumerate(cleaned_words):
            if word in FILLER_WORDS:
                filler_count += 1
            # Check immediate repetition (e.g. "if if", "we we")
            if i > 0 and word == cleaned_words[i - 1]:
                repetition_count += 1

        disfluency_ratio = min(1.0, (filler_count + repetition_count) / max(1, len(cleaned_words)))

        # 4. Type-Token Ratio (TTR)
        unique_tokens = set(cleaned_words)
        ttr = len(unique_tokens) / max(1, len(cleaned_words))

        # 5. Composite Acoustic Friction Score via Sigmoid Function
        # Weights: w1=0.30 (WPM anomaly), w2=0.40 (pause density), w3=0.30 (disfluency)
        # Scaled to normalize [0.0, 1.0]
        linear_val = (
            0.30 * min(3.0, wpm_anomaly_z)
            + 0.40 * (pause_density * 4.0)
            + 0.30 * (disfluency_ratio * 4.0)
            - 1.2
        )
        friction_score = 1.0 / (1.0 + math.exp(-linear_val))
        friction_score = min(1.0, max(0.0, friction_score))

        # Spike detection criteria
        is_spike = (
            friction_score >= 0.45
            or wpm_anomaly_z >= 1.85
            or pause_density >= 0.35
            or disfluency_ratio >= 0.20
        )

        # Determine primary contributing signal
        if disfluency_ratio >= 0.15 and (disfluency_ratio * 4.0) >= pause_density * 3.0:
            primary_signal = "disfluency"
        elif pause_density >= 0.25:
            primary_signal = "pause_density"
        elif wpm_anomaly_z >= 1.5:
            primary_signal = "acoustic_wpm"
        else:
            primary_signal = "semantic"

        return SegmentSignalMetrics(
            segment_id=segment.id,
            start_time=segment.start_time,
            end_time=segment.end_time,
            duration_seconds=round(duration, 2),
            word_count=word_count,
            wpm=round(wpm, 1),
            wpm_anomaly_z=round(wpm_anomaly_z, 2),
            pause_time_seconds=round(pause_time, 2),
            pause_density=round(pause_density, 3),
            filler_count=filler_count,
            repetition_count=repetition_count,
            disfluency_ratio=round(disfluency_ratio, 3),
            type_token_ratio=round(ttr, 3),
            acoustic_friction_score=round(friction_score, 3),
            is_confusion_spike=is_spike,
            primary_signal=primary_signal,
        )

    def analyze_lecture(
        self,
        segments: List[TranscriptSegment],
    ) -> List[SegmentSignalMetrics]:
        """Runs full signal extraction across all segments in a lecture."""
        baseline = self.compute_lecture_baseline(segments)
        return [self.compute_segment_signals(seg, baseline) for seg in segments]


signal_engine = SignalEngine()
