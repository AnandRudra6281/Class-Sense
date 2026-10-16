import math
import pytest
from app.models.transcript import TranscriptSegment
from app.services.signal_engine import BaselineMetrics, SignalEngine, signal_engine


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
    # seg1: 120 words in 60s -> 120 WPM; seg2: 160 words in 60s -> 160 WPM
    assert baseline.mean_wpm == 140.0
    assert baseline.std_wpm == 20.0


def test_speech_rate_anomaly_z_score():
    engine = SignalEngine()
    baseline = BaselineMetrics(mean_wpm=140.0, std_wpm=20.0, total_segments=10, total_duration=600.0)

    # Normal delivery: 140 WPM -> z = 0.0
    normal_words = [{"word": f"w{i}", "start": float(i) * 0.42, "end": float(i) * 0.42 + 0.3} for i in range(140)]
    normal_seg = TranscriptSegment(
        id="norm1",
        lecture_id="lec1",
        start_time=0.0,
        end_time=60.0,
        text="Normal lecture delivery text.",
        words=normal_words,
        coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    res_norm = engine.compute_segment_signals(normal_seg, baseline)
    assert res_norm.wpm == 140.0
    assert res_norm.wpm_anomaly_z == 0.0

    # Rushed delivery: 200 WPM -> z = |200 - 140| / 20 = 3.0
    rushed_words = [{"word": f"w{i}", "start": float(i) * 0.3, "end": float(i) * 0.3 + 0.2} for i in range(200)]
    rushed_seg = TranscriptSegment(
        id="rush1",
        lecture_id="lec1",
        start_time=0.0,
        end_time=60.0,
        text="Very fast lecture delivery text.",
        words=rushed_words,
        coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    res_rush = engine.compute_segment_signals(rushed_seg, baseline)
    assert res_rush.wpm == 200.0
    assert res_rush.wpm_anomaly_z == 3.0


def test_pause_density_calculation():
    engine = SignalEngine()
    baseline = BaselineMetrics(mean_wpm=120.0, std_wpm=20.0, total_segments=5, total_duration=100.0)

    # 10 second segment with 4 seconds of pauses:
    # word 1: 0.0 to 1.0 (pause 2.0s until 3.0)
    # word 2: 3.0 to 4.0 (pause 2.0s until 6.0)
    # word 3: 6.0 to 10.0
    words = [
        {"word": "Let's", "start": 0.0, "end": 1.0},
        {"word": "think", "start": 3.0, "end": 4.0},
        {"word": "about", "start": 6.0, "end": 10.0},
    ]
    seg = TranscriptSegment(
        id="pause_seg",
        lecture_id="lec1",
        start_time=0.0,
        end_time=10.0,
        text="Let's think about",
        words=words,
        coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    res = engine.compute_segment_signals(seg, baseline)
    assert res.pause_time_seconds == 4.0
    assert res.pause_density == 0.40  # 4s / 10s


def test_disfluency_and_repetition_detection():
    engine = SignalEngine()
    baseline = BaselineMetrics(mean_wpm=120.0, std_wpm=20.0, total_segments=5, total_duration=100.0)

    # Text with fillers ("um", "uh", "like") and repetition ("if if")
    # Cleaned words: ["um", "if", "if", "we", "like", "consider", "uh", "this"] -> 8 words
    # Fillers: um, like, uh (3)
    # Repetitions: "if" repeated once (1)
    # Total disfluency count = 4; ratio = 4 / 8 = 0.50
    words = [
        {"word": "Um", "start": 0.0, "end": 0.5},
        {"word": "if", "start": 0.6, "end": 0.9},
        {"word": "if", "start": 1.0, "end": 1.3},
        {"word": "we", "start": 1.4, "end": 1.7},
        {"word": "like", "start": 1.8, "end": 2.2},
        {"word": "consider", "start": 2.3, "end": 2.8},
        {"word": "uh", "start": 2.9, "end": 3.2},
        {"word": "this", "start": 3.3, "end": 3.8},
    ]
    seg = TranscriptSegment(
        id="disfl_seg",
        lecture_id="lec1",
        start_time=0.0,
        end_time=4.0,
        text="Um if if we like consider uh this",
        words=words,
        coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    res = engine.compute_segment_signals(seg, baseline)
    assert res.filler_count == 3
    assert res.repetition_count == 1
    assert res.disfluency_ratio == 0.50
    assert res.is_confusion_spike is True
    assert res.primary_signal == "disfluency"


def test_type_token_ratio_lexical_variety():
    engine = SignalEngine()
    baseline = BaselineMetrics()

    # Highly repetitive words: "eigenvalue eigenvalue eigenvalue matrix matrix"
    # Total = 5, unique = 2 -> TTR = 2/5 = 0.40
    words = [
        {"word": "eigenvalue", "start": 0.0, "end": 0.8},
        {"word": "eigenvalue", "start": 0.9, "end": 1.6},
        {"word": "eigenvalue", "start": 1.7, "end": 2.4},
        {"word": "matrix", "start": 2.5, "end": 3.0},
        {"word": "matrix", "start": 3.1, "end": 3.6},
    ]
    seg = TranscriptSegment(
        id="ttr_seg",
        lecture_id="lec1",
        start_time=0.0,
        end_time=4.0,
        text="eigenvalue eigenvalue eigenvalue matrix matrix",
        words=words,
        coordinates={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    res = engine.compute_segment_signals(seg, baseline)
    assert res.type_token_ratio == 0.40
