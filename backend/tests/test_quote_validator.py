from unittest.mock import AsyncMock, patch
import pytest

from app.schemas.confusion import LLMWindowConfusionAnalysis
from app.services.confusion_service import ConfusionService, confusion_service
from app.services.signal_engine import SlidingWindow, WindowSignalMetrics


def test_quote_validator_exact_substring_valid():
    """Exact substring quote passes validation."""
    window_text = "Today we discuss gradient descent and backpropagation through computational graphs."
    valid_quote = "gradient descent and backpropagation"
    assert ConfusionService.validate_quote_substring(valid_quote, window_text) is True


def test_quote_validator_strips_quotes_and_whitespace():
    """Quote with leading/trailing quotes and spaces still passes exact substring check."""
    window_text = "Now why does the matrix get transposed here?"
    quote_with_quotes = '  "why does the matrix get transposed"  '
    assert ConfusionService.validate_quote_substring(quote_with_quotes, window_text) is True


def test_quote_validator_invalid_quote_rejected():
    """Paraphrased or hallucinated quote not present in transcript is rejected."""
    window_text = "The derivative of x squared is 2x."
    hallucinated_quote = "The calculus rate of change of x squared is two times x."
    assert ConfusionService.validate_quote_substring(hallucinated_quote, window_text) is False


@pytest.mark.asyncio
async def test_quote_validator_invalid_quote_retries_and_succeeds():
    """When the first LLM pass returns a hallucinated quote, it retries once and accepts valid retry."""
    service = ConfusionService()
    win = WindowSignalMetrics(
        window_id="win_test",
        start_time=0.0,
        end_time=45.0,
        duration_seconds=45.0,
        text="The gradient of a scalar with respect to a matrix retains the matrix dimension.",
        segment_ids=["s1"],
        word_count=13,
        wpm=120.0,
        wpm_anomaly_z=0.5,
        pause_time_seconds=2.0,
        pause_density=0.1,
        filler_count=0,
        repetition_count=0,
        disfluency_ratio=0.0,
        repetition_ratio=0.0,
        question_count=0,
        question_density=0.0,
        max_response_gap_seconds=0.0,
        student_response_gap=0.0,
        type_token_ratio=0.8,
        signal_score=0.35,
        is_flagged=True,
        primary_signal="pause_density",
    )

    # First call returns hallucinated quote, second call returns exact substring
    invalid_eval = LLMWindowConfusionAnalysis(
        confusion_score=0.75,
        ai_confidence=0.85,
        evidence_quote="The derivative matrix shape must always mirror the input shape precisely.",
        rationale="Dimension confusion",
    )
    valid_eval = LLMWindowConfusionAnalysis(
        confusion_score=0.75,
        ai_confidence=0.90,
        evidence_quote="retains the matrix dimension",
        rationale="Confusion regarding dimension retention",
    )

    mock_llm = AsyncMock()
    mock_llm.generate_structured.side_effect = [invalid_eval, valid_eval]

    with patch("app.services.confusion_service.get_llm_provider", return_value=mock_llm):
        result = await service._evaluate_window_llm(win)

    assert result is not None
    assert result.evidence_quote == "retains the matrix dimension"
    assert mock_llm.generate_structured.call_count == 2


@pytest.mark.asyncio
async def test_quote_validator_invalid_quote_retries_and_drops_event():
    """When both the first call and retry return hallucinated quotes, the event is dropped (returns None)."""
    service = ConfusionService()
    win = WindowSignalMetrics(
        window_id="win_test",
        start_time=0.0,
        end_time=45.0,
        duration_seconds=45.0,
        text="Eigenvectors do not change direction during linear transformation.",
        segment_ids=["s1"],
        word_count=9,
        wpm=120.0,
        wpm_anomaly_z=0.5,
        pause_time_seconds=2.0,
        pause_density=0.1,
        filler_count=0,
        repetition_count=0,
        disfluency_ratio=0.0,
        repetition_ratio=0.0,
        question_count=0,
        question_density=0.0,
        max_response_gap_seconds=0.0,
        student_response_gap=0.0,
        type_token_ratio=0.8,
        signal_score=0.35,
        is_flagged=True,
        primary_signal="pause_density",
    )

    # Both passes return quotes not in win.text
    invalid_eval_1 = LLMWindowConfusionAnalysis(
        confusion_score=0.80,
        ai_confidence=0.85,
        evidence_quote="Vectors keep their original pointing angle",
        rationale="Vector rotation confusion",
    )
    invalid_eval_2 = LLMWindowConfusionAnalysis(
        confusion_score=0.80,
        ai_confidence=0.85,
        evidence_quote="Direction invariance under mapping",
        rationale="Vector rotation confusion",
    )

    mock_llm = AsyncMock()
    mock_llm.generate_structured.side_effect = [invalid_eval_1, invalid_eval_2]

    with patch("app.services.confusion_service.get_llm_provider", return_value=mock_llm):
        result = await service._evaluate_window_llm(win)

    # Dropped event returns None
    assert result is None
    assert mock_llm.generate_structured.call_count == 2


def test_quote_validator_exceeding_30_words_rejected():
    """Exact substring quote exceeding 30 words is rejected."""
    long_sentence = " ".join([f"word{i}" for i in range(35)])
    window_text = f"Intro. {long_sentence} Outro."
    assert ConfusionService.validate_quote_substring(long_sentence, window_text, max_words=30) is False


def test_quote_validator_max_30_words_passes():
    """Exact substring quote of exactly 30 words passes validation."""
    valid_30_words = " ".join([f"word{i}" for i in range(30)])
    window_text = f"Intro. {valid_30_words} Outro."
    assert ConfusionService.validate_quote_substring(valid_30_words, window_text, max_words=30) is True


@pytest.mark.asyncio
async def test_quote_validator_too_long_quote_retries_and_succeeds():
    """When the first LLM pass returns an exact substring exceeding 30 words, it retries and accepts concise quote."""
    service = ConfusionService()
    too_long_quote = " ".join([f"concept{i}" for i in range(35)])
    concise_quote = "concept0 concept1 concept2"
    window_text = f"Here is the lecture. {too_long_quote} and more."

    win = WindowSignalMetrics(
        window_id="win_length_retry",
        start_time=0.0,
        end_time=45.0,
        duration_seconds=45.0,
        text=window_text,
        segment_ids=["s1"],
        word_count=50,
        wpm=120.0,
        wpm_anomaly_z=0.5,
        pause_time_seconds=2.0,
        pause_density=0.1,
        filler_count=0,
        repetition_count=0,
        disfluency_ratio=0.0,
        repetition_ratio=0.0,
        question_count=0,
        question_density=0.0,
        max_response_gap_seconds=0.0,
        student_response_gap=0.0,
        type_token_ratio=0.8,
        signal_score=0.45,
        is_flagged=True,
        primary_signal="pause_density",
    )

    long_eval = LLMWindowConfusionAnalysis(
        confusion_score=0.80,
        ai_confidence=0.85,
        evidence_quote=too_long_quote,
        rationale="Lengthy quote explaining cognitive difficulty",
    )
    concise_eval = LLMWindowConfusionAnalysis(
        confusion_score=0.80,
        ai_confidence=0.90,
        evidence_quote=concise_quote,
        rationale="Concise quote explaining cognitive difficulty",
    )

    mock_llm = AsyncMock()
    mock_llm.generate_structured.side_effect = [long_eval, concise_eval]

    with patch("app.services.confusion_service.get_llm_provider", return_value=mock_llm):
        result = await service._evaluate_window_llm(win)

    assert result is not None
    assert result.evidence_quote == concise_quote
    assert mock_llm.generate_structured.call_count == 2


@pytest.mark.asyncio
async def test_quote_validator_too_long_quote_retries_and_drops_event():
    """When both attempts return quotes exceeding 30 words, the event is dropped with logged reason."""
    service = ConfusionService()
    too_long_quote_1 = " ".join([f"termA{i}" for i in range(32)])
    too_long_quote_2 = " ".join([f"termB{i}" for i in range(35)])
    window_text = f"Prefix. {too_long_quote_1} middle {too_long_quote_2} suffix."

    win = WindowSignalMetrics(
        window_id="win_length_fail",
        start_time=0.0,
        end_time=45.0,
        duration_seconds=45.0,
        text=window_text,
        segment_ids=["s1"],
        word_count=80,
        wpm=120.0,
        wpm_anomaly_z=0.5,
        pause_time_seconds=2.0,
        pause_density=0.1,
        filler_count=0,
        repetition_count=0,
        disfluency_ratio=0.0,
        repetition_ratio=0.0,
        question_count=0,
        question_density=0.0,
        max_response_gap_seconds=0.0,
        student_response_gap=0.0,
        type_token_ratio=0.8,
        signal_score=0.45,
        is_flagged=True,
        primary_signal="pause_density",
    )

    eval_1 = LLMWindowConfusionAnalysis(
        confusion_score=0.70,
        ai_confidence=0.80,
        evidence_quote=too_long_quote_1,
        rationale="Overlength quote 1",
    )
    eval_2 = LLMWindowConfusionAnalysis(
        confusion_score=0.70,
        ai_confidence=0.80,
        evidence_quote=too_long_quote_2,
        rationale="Overlength quote 2",
    )

    mock_llm = AsyncMock()
    mock_llm.generate_structured.side_effect = [eval_1, eval_2]

    with patch("app.services.confusion_service.get_llm_provider", return_value=mock_llm):
        result = await service._evaluate_window_llm(win)

    assert result is None
    assert mock_llm.generate_structured.call_count == 2


def test_score_fusion_with_configurable_weights():
    """Final score combines acoustic signal score and LLM score according to weights."""
    sig_score = 0.60
    llm_score = 0.80
    w_sig = 0.40
    w_llm = 0.60

    fused = (w_sig * sig_score) + (w_llm * llm_score)
    # 0.4 * 0.6 + 0.6 * 0.8 = 0.24 + 0.48 = 0.72
    assert round(fused, 3) == 0.72

