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

QUESTION_STARTERS = {
    "why",
    "how",
    "what",
    "does",
    "do",
    "can",
    "could",
    "is",
    "are",
    "who",
    "where",
    "when",
    "which",
    "should",
    "would",
}


class BaselineMetrics(BaseModel):
    mean_wpm: float = 140.0
    std_wpm: float = 25.0
    total_segments: int = 0
    total_duration: float = 0.0


class SlidingWindow(BaseModel):
    window_id: str
    start_time: float
    end_time: float
    duration_seconds: float
    text: str
    words: List[Dict[str, Any]] = Field(default_factory=list)
    segment_ids: List[str] = Field(default_factory=list)


class WindowSignalMetrics(BaseModel):
    window_id: str
    start_time: float
    end_time: float
    duration_seconds: float
    text: str
    segment_ids: List[str]
    word_count: int
    wpm: float
    wpm_anomaly_z: float
    pause_time_seconds: float
    pause_density: float
    filler_count: int
    repetition_count: int
    disfluency_ratio: float
    repetition_ratio: float
    question_count: int
    question_density: float
    max_response_gap_seconds: float
    student_response_gap: float
    type_token_ratio: float
    signal_score: float
    is_flagged: bool
    primary_signal: str
    baseline_status: str = "sufficient"


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
    Computes mathematical acoustic and linguistic indicators of cognitive hesitation
    using 30-60s sliding windows over lecture transcripts following docs/CONFUSION_METHOD.md.
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

    def build_sliding_windows(
        self,
        segments: List[TranscriptSegment],
        window_size: float = 45.0,
        step: float = 15.0,
    ) -> List[SlidingWindow]:
        """
        Builds 30-60s sliding windows across sorted transcript segments.
        If lecture duration is <= window_size, returns a single window.
        """
        if not segments:
            return []

        total_duration = max(s.end_time for s in segments)
        if total_duration <= window_size:
            all_words = []
            for s in segments:
                if s.words:
                    all_words.extend(s.words)
            full_text = " ".join(s.text.strip() for s in segments if s.text.strip())
            return [
                SlidingWindow(
                    window_id="win_000",
                    start_time=segments[0].start_time,
                    end_time=total_duration,
                    duration_seconds=round(total_duration - segments[0].start_time, 2),
                    text=full_text,
                    words=all_words,
                    segment_ids=[s.id for s in segments],
                )
            ]

        windows: List[SlidingWindow] = []
        win_start = 0.0
        idx = 0

        while win_start < total_duration:
            win_end = min(total_duration, win_start + window_size)
            win_dur = win_end - win_start

            # Find overlapping segments
            overlapping_segs = [
                s for s in segments
                if not (s.end_time <= win_start or s.start_time >= win_end)
            ]

            # Gather words belonging to this window
            win_words: List[Dict[str, Any]] = []
            for s in overlapping_segs:
                if s.words:
                    for w in s.words:
                        w_start = float(w.get("start", s.start_time))
                        w_end = float(w.get("end", s.end_time))
                        if not (w_end <= win_start or w_start >= win_end):
                            win_words.append(w)

            # Build window text
            if win_words:
                win_text = " ".join(str(w.get("word", "")).strip() for w in win_words if str(w.get("word", "")).strip())
            else:
                win_text = " ".join(s.text.strip() for s in overlapping_segs if s.text.strip())

            if win_text.strip():
                windows.append(
                    SlidingWindow(
                        window_id=f"win_{idx:03d}",
                        start_time=round(win_start, 2),
                        end_time=round(win_end, 2),
                        duration_seconds=round(win_dur, 2),
                        text=win_text.strip(),
                        words=win_words,
                        segment_ids=[s.id for s in overlapping_segs],
                    )
                )
                idx += 1

            if win_end >= total_duration:
                break
            win_start += step

        return windows

    @staticmethod
    def count_questions(text: str) -> int:
        """Counts direct and indirect pedagogical question occurrences in transcript text."""
        # 1. Count question marks
        qmark_count = text.count("?")
        if qmark_count > 0:
            return qmark_count

        # 2. Check sentence starters if punctuation is absent
        sentences = re.split(r"[.!\n]+", text)
        q_count = 0
        for s in sentences:
            tokens = s.strip().lower().split()
            if tokens and tokens[0] in QUESTION_STARTERS:
                q_count += 1
        return q_count

    @staticmethod
    def compute_question_density(question_count: int, duration_seconds: float) -> float:
        """
        Computes question density per minute normalized to [0.0, 1.0].
        A rate of >= 3.0 questions/minute maps to 1.0.
        """
        duration_min = max(0.2, duration_seconds / 60.0)
        q_per_min = question_count / duration_min
        return round(min(1.0, max(0.0, q_per_min / 3.0)), 3)

    @staticmethod
    def compute_student_response_gap(
        words_data: List[Dict[str, Any]],
        text: str,
        duration_seconds: float,
    ) -> tuple[float, float]:
        """
        Calculates post-question hesitation/wait-time latency in seconds and normalized score [0, 1].
        A post-question silence >= 4.0s maps to 1.0.
        """
        if not words_data:
            # If no word timestamps, check if text has question and long pause is absent
            return 0.0, 0.0

        max_gap = 0.0
        for i in range(len(words_data) - 1):
            curr_w = str(words_data[i].get("word", "")).strip()
            # If current word ends with question mark or is followed by sentence boundary
            if curr_w.endswith("?"):
                curr_end = float(words_data[i].get("end", 0.0))
                next_start = float(words_data[i + 1].get("start", 0.0))
                gap = max(0.0, next_start - curr_end)
                if gap > max_gap:
                    max_gap = gap

        # If no explicit '?' on words, check for any pause > 2.0s in a window with questions
        if max_gap == 0.0 and "?" in text:
            for i in range(len(words_data) - 1):
                curr_end = float(words_data[i].get("end", 0.0))
                next_start = float(words_data[i + 1].get("start", 0.0))
                gap = max(0.0, next_start - curr_end)
                if gap >= 1.5 and gap > max_gap:
                    max_gap = gap

        normalized_gap = min(1.0, max(0.0, max_gap / 4.0))
        return round(max_gap, 2), round(normalized_gap, 3)

    def compute_window_signals(
        self,
        window: SlidingWindow,
        baseline: BaselineMetrics,
        weights: Optional[Dict[str, float]] = None,
        baseline_status: str = "sufficient",
    ) -> WindowSignalMetrics:
        """
        Computes all 6 signals over a 30-60s sliding window:
        1. speech_rate_anomaly (z-score if >=3 windows, absolute thresholds if <3)
        2. pause_density
        3. disfluency_ratio
        4. repetition_ratio
        5. question_density
        6. student_response_gap
        """
        duration = max(0.5, window.duration_seconds)
        words_data = window.words

        if not words_data:
            tokens = window.text.split()
            word_count = len(tokens)
            wpm = (word_count / duration) * 60.0
            words_data = [{"word": t, "start": window.start_time, "end": window.end_time} for t in tokens]
        else:
            word_count = len(words_data)
            wpm = (word_count / duration) * 60.0

        # 1. Speech rate anomaly: statistical z-score if >=3 windows, absolute threshold if <3 windows
        if baseline_status == "insufficient baseline":
            if wpm < 110.0:
                abs_wpm_anomaly = min(1.0, max(0.0, (110.0 - wpm) / 50.0))
            elif wpm > 180.0:
                abs_wpm_anomaly = min(1.0, max(0.0, (wpm - 180.0) / 50.0))
            else:
                abs_wpm_anomaly = 0.0
            norm_wpm = abs_wpm_anomaly
            wpm_anomaly_z = round(norm_wpm * 2.5, 2)
        else:
            wpm_anomaly_z = abs(wpm - baseline.mean_wpm) / (baseline.std_wpm + 1e-5)
            norm_wpm = min(1.0, wpm_anomaly_z / 2.5)

        # 2. Pause and silence density
        pause_time = 0.0
        for i in range(len(words_data) - 1):
            curr_end = float(words_data[i].get("end", 0.0))
            next_start = float(words_data[i + 1].get("start", 0.0))
            gap = next_start - curr_end
            if gap >= 0.20:
                pause_time += gap
        pause_density = min(1.0, max(0.0, pause_time / duration))

        # 3. Disfluency & 4. Repetition
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
            if i > 0 and word == cleaned_words[i - 1]:
                repetition_count += 1

        total_words_count = max(1, len(cleaned_words))
        disfluency_ratio = min(1.0, filler_count / total_words_count)
        repetition_ratio = min(1.0, repetition_count / total_words_count)

        # 5. Question Density
        q_count = self.count_questions(window.text)
        question_density = self.compute_question_density(q_count, duration)

        # 6. Student Response Gap
        max_gap_sec, response_gap_norm = self.compute_student_response_gap(
            words_data,
            window.text,
            duration,
        )

        # Type-Token Ratio
        unique_tokens = set(cleaned_words)
        ttr = len(unique_tokens) / total_words_count

        # Configurable signal weights
        w = weights or {
            "pause": 0.20,
            "wpm": 0.20,
            "disfluency": 0.15,
            "repetition": 0.15,
            "question": 0.15,
            "response_gap": 0.15,
        }

        # Composite signal score normalized to [0, 1]
        norm_pause = min(1.0, pause_density * 2.5)
        norm_disfl = min(1.0, disfluency_ratio * 4.0)
        norm_rep = min(1.0, repetition_ratio * 4.0)
        norm_q = question_density
        norm_gap = response_gap_norm

        composite_signal_score = (
            w.get("pause", 0.20) * norm_pause
            + w.get("wpm", 0.20) * norm_wpm
            + w.get("disfluency", 0.15) * norm_disfl
            + w.get("repetition", 0.15) * norm_rep
            + w.get("question", 0.15) * norm_q
            + w.get("response_gap", 0.15) * norm_gap
        )
        composite_signal_score = round(min(1.0, max(0.0, composite_signal_score)), 3)

        # Flagging criteria: elevated composite score or significant individual signal spike
        if baseline_status == "insufficient baseline":
            wpm_spike = norm_wpm >= 0.70
        else:
            wpm_spike = wpm_anomaly_z >= 1.75

        is_flagged = (
            composite_signal_score >= 0.28
            or wpm_spike
            or pause_density >= 0.30
            or (disfluency_ratio + repetition_ratio) >= 0.15
            or question_density >= 0.50
            or response_gap_norm >= 0.40
        )

        # Determine primary signal
        signals_map = {
            "pause_density": norm_pause,
            "acoustic_wpm": norm_wpm,
            "disfluency": norm_disfl,
            "repetition": norm_rep,
            "question_density": norm_q,
            "student_response_gap": norm_gap,
        }
        primary_signal = max(signals_map, key=signals_map.get)

        return WindowSignalMetrics(
            window_id=window.window_id,
            start_time=window.start_time,
            end_time=window.end_time,
            duration_seconds=round(duration, 2),
            text=window.text,
            segment_ids=window.segment_ids,
            word_count=word_count,
            wpm=round(wpm, 1),
            wpm_anomaly_z=round(wpm_anomaly_z, 2),
            pause_time_seconds=round(pause_time, 2),
            pause_density=round(pause_density, 3),
            filler_count=filler_count,
            repetition_count=repetition_count,
            disfluency_ratio=round(disfluency_ratio, 3),
            repetition_ratio=round(repetition_ratio, 3),
            question_count=q_count,
            question_density=question_density,
            max_response_gap_seconds=max_gap_sec,
            student_response_gap=response_gap_norm,
            type_token_ratio=round(ttr, 3),
            signal_score=composite_signal_score,
            is_flagged=is_flagged,
            primary_signal=primary_signal,
            baseline_status=baseline_status,
        )

    def analyze_lecture_windows(
        self,
        segments: List[TranscriptSegment],
        window_size: float = 45.0,
        step: float = 15.0,
        weights: Optional[Dict[str, float]] = None,
    ) -> List[WindowSignalMetrics]:
        """Runs sliding window generation and computes all 6 signals across all windows.
        Statistical baselines (z-scores) need >= 3 windows; with fewer, fall back to
        absolute thresholds and record 'insufficient baseline'.
        """
        windows = self.build_sliding_windows(segments, window_size=window_size, step=step)
        if len(windows) >= 3:
            baseline_status = "sufficient"
            baseline = self.compute_lecture_baseline(segments)
        else:
            baseline_status = "insufficient baseline"
            baseline = BaselineMetrics(mean_wpm=140.0, std_wpm=25.0)

        return [
            self.compute_window_signals(
                win,
                baseline,
                weights=weights,
                baseline_status=baseline_status,
            )
            for win in windows
        ]

    # Backward compatibility with existing segment-level tests
    def compute_segment_signals(
        self,
        segment: TranscriptSegment,
        baseline: BaselineMetrics,
    ) -> SegmentSignalMetrics:
        """Computes signals for a single segment for backwards compatibility."""
        duration = max(0.1, segment.end_time - segment.start_time)
        words_data: List[Dict[str, Any]] = segment.words if segment.words else []

        if not words_data:
            tokens = segment.text.split()
            word_count = len(tokens)
            wpm = (word_count / duration) * 60.0
            words_data = [{"word": t, "start": segment.start_time, "end": segment.end_time} for t in tokens]
        else:
            word_count = len(words_data)
            wpm = (word_count / duration) * 60.0

        wpm_anomaly_z = abs(wpm - baseline.mean_wpm) / (baseline.std_wpm + 1e-5)

        pause_time = 0.0
        for i in range(len(words_data) - 1):
            curr_end = float(words_data[i].get("end", 0.0))
            next_start = float(words_data[i + 1].get("start", 0.0))
            gap = next_start - curr_end
            if gap >= 0.20:
                pause_time += gap

        pause_density = min(1.0, max(0.0, pause_time / duration))

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
            if i > 0 and word == cleaned_words[i - 1]:
                repetition_count += 1

        disfluency_ratio = min(1.0, (filler_count + repetition_count) / max(1, len(cleaned_words)))
        unique_tokens = set(cleaned_words)
        ttr = len(unique_tokens) / max(1, len(cleaned_words))

        linear_val = (
            0.30 * min(3.0, wpm_anomaly_z)
            + 0.40 * (pause_density * 4.0)
            + 0.30 * (disfluency_ratio * 4.0)
            - 1.2
        )
        friction_score = 1.0 / (1.0 + math.exp(-linear_val))
        friction_score = min(1.0, max(0.0, friction_score))

        is_spike = (
            friction_score >= 0.45
            or wpm_anomaly_z >= 1.85
            or pause_density >= 0.35
            or disfluency_ratio >= 0.20
        )

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
