import math
import pytest
from app.models.transcript import TranscriptSegment
from app.services.signal_engine import (
    BaselineMetrics,
    SignalEngine,
    SlidingWindow,
    signal_engine,
)


def test_baseline_calculation_empty_and_nominal():
    engine = SignalEngine()
    empty_baseline = engine.compute_lecture_baseline([])
    assert empty_baseline.mean_wpm == 140.0
    assert empty_baseline.total_segments == 0

    seg1 = TranscriptSegment(
        id="s1",
        lecture_id="lec1",
        start_time=0.0,
        end_time=60.0,
        text="This is a test of sixty words per minute lecture delivery for testing purposes here.",
        words=[{"word": f"w{i}", "start": float(i), "end": float(i) + 0.8} for i in range(120)],
        coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    seg2 = TranscriptSegment(
        id="s2",
        lecture_id="lec1",
        start_time=60.0,
        end_time=120.0,
        text="Second minute of lecture delivery.",
        words=[{"word": f"w{i}", "start": 60.0 + float(i), "end": 60.0 + float(i) + 0.8} for i in range(160)],
        coordinates={"x": 50.0, "y": 0.0, "z": 0.0},
    )

    baseline = engine.compute_lecture_baseline([seg1, seg2])
    assert baseline.total_segments == 2
    assert baseline.total_duration == 120.0
    assert baseline.mean_wpm == 140.0
    assert baseline.std_wpm == 20.0


# Signal 1: Speech Rate Anomaly
def test_signal_speech_rate_anomaly():
    engine = SignalEngine()
    baseline = BaselineMetrics(mean_wpm=140.0, std_wpm=20.0)

    # Window with 200 WPM: 150 words in 45s -> 200 WPM
    words = [{"word": f"w{i}", "start": float(i) * 0.3, "end": float(i) * 0.3 + 0.25} for i in range(150)]
    win = SlidingWindow(
        window_id="win_rush",
        start_time=0.0,
        end_time=45.0,
        duration_seconds=45.0,
        text=" ".join(w["word"] for w in words),
        words=words,
    )
    metrics = engine.compute_window_signals(win, baseline)
    assert metrics.wpm == 200.0
    # |200 - 140| / 20 = 3.0
    assert metrics.wpm_anomaly_z == 3.0
    assert metrics.is_flagged is True


# Signal 2: Pause Density
def test_signal_pause_density():
    engine = SignalEngine()
    baseline = BaselineMetrics(mean_wpm=120.0, std_wpm=20.0)

    # 45 second window with three words separated by 10s and 8s pauses
    # pause time = 10s + 8s = 18s; pause density = 18 / 45 = 0.40
    words = [
        {"word": "Concept", "start": 0.0, "end": 2.0},
        {"word": "definition", "start": 12.0, "end": 14.0},
        {"word": "follows", "start": 22.0, "end": 24.0},
    ]
    win = SlidingWindow(
        window_id="win_pause",
        start_time=0.0,
        end_time=45.0,
        duration_seconds=45.0,
        text="Concept definition follows",
        words=words,
    )
    metrics = engine.compute_window_signals(win, baseline)
    assert metrics.pause_time_seconds == 18.0
    assert metrics.pause_density == 0.40
    assert metrics.is_flagged is True


# Signal 3: Disfluency Ratio
def test_signal_disfluency():
    engine = SignalEngine()
    baseline = BaselineMetrics()

    # Window with filler words: "um", "uh", "actually", "like" (4 fillers out of 10 words = 0.40)
    tokens = ["um", "so", "uh", "the", "eigenvalues", "actually", "represent", "like", "the", "stretch"]
    words = [{"word": t, "start": float(i) * 3.0, "end": float(i) * 3.0 + 1.0} for i, t in enumerate(tokens)]
    win = SlidingWindow(
        window_id="win_disfl",
        start_time=0.0,
        end_time=45.0,
        duration_seconds=45.0,
        text=" ".join(tokens),
        words=words,
    )
    metrics = engine.compute_window_signals(win, baseline)
    assert metrics.filler_count == 4
    assert metrics.disfluency_ratio == 0.40
    assert metrics.is_flagged is True


# Signal 4: Repetition Ratio
def test_signal_repetition():
    engine = SignalEngine()
    baseline = BaselineMetrics()

    # Window with immediate repeated words: "if if", "we we" (2 repetitions out of 10 words = 0.20)
    tokens = ["if", "if", "we", "we", "compute", "the", "matrix", "inverse", "here", "today"]
    words = [{"word": t, "start": float(i) * 3.0, "end": float(i) * 3.0 + 1.0} for i, t in enumerate(tokens)]
    win = SlidingWindow(
        window_id="win_rep",
        start_time=0.0,
        end_time=45.0,
        duration_seconds=45.0,
        text=" ".join(tokens),
        words=words,
    )
    metrics = engine.compute_window_signals(win, baseline)
    assert metrics.repetition_count == 2
    assert metrics.repetition_ratio == 0.20


# Signal 5: Question Density
def test_signal_question_density():
    engine = SignalEngine()
    baseline = BaselineMetrics()

    # Window of 40s with 3 questions -> rate = 3 / (40 / 60) = 4.5 questions/min
    # Normalized density: min(1.0, 4.5 / 3.0) = 1.0
    text = "Why does the gradient transpose? Does anyone know? Can we invert this?"
    tokens = text.split()
    words = [{"word": t, "start": float(i) * 2.0, "end": float(i) * 2.0 + 1.0} for i, t in enumerate(tokens)]
    win = SlidingWindow(
        window_id="win_q",
        start_time=0.0,
        end_time=40.0,
        duration_seconds=40.0,
        text=text,
        words=words,
    )
    metrics = engine.compute_window_signals(win, baseline)
    assert metrics.question_count == 3
    assert metrics.question_density == 1.0
    assert metrics.is_flagged is True


# Signal 6: Student Response Gap
def test_signal_student_response_gap():
    engine = SignalEngine()
    baseline = BaselineMetrics()

    # Question followed by a 3.5s silence gap before next utterance
    words = [
        {"word": "Any", "start": 0.0, "end": 0.5},
        {"word": "questions?", "start": 0.6, "end": 1.2},
        {"word": "Okay,", "start": 4.7, "end": 5.2},  # gap = 4.7 - 1.2 = 3.5 seconds
        {"word": "moving", "start": 5.3, "end": 5.8},
        {"word": "on.", "start": 5.9, "end": 6.5},
    ]
    win = SlidingWindow(
        window_id="win_gap",
        start_time=0.0,
        end_time=45.0,
        duration_seconds=45.0,
        text="Any questions? Okay, moving on.",
        words=words,
    )
    metrics = engine.compute_window_signals(win, baseline)
    assert metrics.max_response_gap_seconds == 3.5
    # Normalized gap: 3.5 / 4.0 = 0.875
    assert metrics.student_response_gap == 0.875
    assert metrics.is_flagged is True


# Sliding Window Generation (30-60s)
def test_signal_sliding_windows_30_60s():
    engine = SignalEngine()
    # Create 3 segments spanning 120 seconds
    seg1 = TranscriptSegment(
        id="seg1",
        lecture_id="lec1",
        start_time=0.0,
        end_time=40.0,
        text="Part one of lecture.",
        words=[{"word": "Part", "start": 0.0, "end": 1.0}],
        coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    seg2 = TranscriptSegment(
        id="seg2",
        lecture_id="lec1",
        start_time=40.0,
        end_time=80.0,
        text="Part two of lecture.",
        words=[{"word": "Part", "start": 40.0, "end": 41.0}],
        coordinates={"x": 30.0, "y": 0.0, "z": 0.0},
    )
    seg3 = TranscriptSegment(
        id="seg3",
        lecture_id="lec1",
        start_time=80.0,
        end_time=120.0,
        text="Part three of lecture.",
        words=[{"word": "Part", "start": 80.0, "end": 81.0}],
        coordinates={"x": 60.0, "y": 0.0, "z": 0.0},
    )

    windows = engine.build_sliding_windows([seg1, seg2, seg3], window_size=45.0, step=15.0)
    assert len(windows) > 1
    # Check that windows obey the 45s size constraint
    for w in windows:
        assert w.duration_seconds <= 45.0
        assert w.start_time >= 0.0
        assert w.end_time <= 120.0


def test_baseline_status_insufficient_vs_sufficient_windows():
    engine = SignalEngine()

    # Case 1: Short clip with < 3 windows (e.g. 25s single segment -> 1 window)
    seg_short = TranscriptSegment(
        id="s_short",
        lecture_id="lec_short",
        start_time=0.0,
        end_time=25.0,
        text="Normal lecture delivery at one hundred and thirty-five words per minute.",
        words=[{"word": f"w{i}", "start": float(i) * 0.44, "end": float(i) * 0.44 + 0.3} for i in range(56)],
        coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
    )

    windows_short = engine.analyze_lecture_windows([seg_short], window_size=45.0, step=15.0)
    assert len(windows_short) < 3
    for w in windows_short:
        assert w.baseline_status == "insufficient baseline"
        # 56 words / 25s * 60 = 134.4 WPM -> inside normal [110, 180] band -> 0 anomaly
        assert w.wpm_anomaly_z == 0.0
        assert w.is_flagged is False

    # Case 2: Long clip with >= 3 windows
    segs_long = [
        TranscriptSegment(
            id=f"s_{i}",
            lecture_id="lec_long",
            start_time=float(i) * 30.0,
            end_time=float(i + 1) * 30.0,
            text=f"Segment {i} lecture delivery content.",
            words=[{"word": f"w{j}", "start": float(i) * 30.0 + float(j) * 0.5, "end": float(i) * 30.0 + float(j) * 0.5 + 0.3} for j in range(60)],
            coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        for i in range(4)
    ]
    windows_long = engine.analyze_lecture_windows(segs_long, window_size=45.0, step=15.0)
    assert len(windows_long) >= 3
    for w in windows_long:
        assert w.baseline_status == "sufficient"
