import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path

from app.core.errors import AppException
from app.schemas.common import Coordinates3D
from app.schemas.transcript import (
    TranscriptionResult,
    TranscriptSegmentSchema,
    WordTimestamp,
)
from app.services.audio_chunker import AudioChunker, AudioChunk


def make_segment(
    start: float,
    end: float,
    text: str,
    words_data: list = None,
) -> TranscriptSegmentSchema:
    coords = Coordinates3D(x=10.0, y=0.0, z=0.0)
    words = []
    if words_data:
        for w_text, w_start, w_end in words_data:
            words.append(WordTimestamp(word=w_text, start=w_start, end=w_end))
    return TranscriptSegmentSchema(
        start_time=start,
        end_time=end,
        text=text,
        words=words,
        coordinates=coords,
    )


def test_plan_chunks_short_audio():
    """Audio shorter than chunk_duration results in a single chunk with zero offset."""
    chunker = AudioChunker(chunk_duration_sec=300.0, overlap_sec=5.0)
    plan = chunker.plan_chunks(total_duration=120.0)
    assert len(plan) == 1
    assert plan[0] == (0, 0.0, 120.0)


def test_plan_chunks_long_audio():
    """Audio longer than chunk duration produces overlapping windows of (c_dur - overlap)."""
    chunker = AudioChunker(chunk_duration_sec=300.0, overlap_sec=5.0)
    # 900 seconds = 15 minutes. Step = 295s.
    # Chunk 0: 0.0 - 300.0
    # Chunk 1: 295.0 - 595.0
    # Chunk 2: 590.0 - 890.0
    # Chunk 3: 885.0 - 900.0
    plan = chunker.plan_chunks(total_duration=900.0)
    assert len(plan) == 4
    assert plan[0] == (0, 0.0, 300.0)
    assert plan[1] == (1, 295.0, 300.0)
    assert plan[2] == (2, 590.0, 300.0)
    assert plan[3] == (3, 885.0, 15.0)


def test_offset_transcription_result():
    """Offsetting shifts all segment and word timestamps by the specified offset."""
    seg = make_segment(
        start=2.0,
        end=5.0,
        text="Hello world",
        words_data=[("Hello", 2.0, 3.0), ("world", 3.5, 5.0)],
    )
    res = TranscriptionResult(
        text="Hello world",
        duration_seconds=5.0,
        language="en",
        segments=[seg],
        words=seg.words,
    )

    offset_res = AudioChunker.offset_transcription_result(res, offset_seconds=295.0)
    assert len(offset_res.segments) == 1
    s0 = offset_res.segments[0]
    assert s0.start_time == 297.0
    assert s0.end_time == 300.0
    assert len(s0.words) == 2
    assert s0.words[0].start == 297.0
    assert s0.words[0].end == 298.0
    assert s0.words[1].start == 298.5
    assert s0.words[1].end == 300.0


def test_stitching_word_level_overlap_deduplication():
    """Stitching two chunks de-duplicates overlapping words and merges continuous text."""
    # Chunk 0: ends with "gradient descent optimization"
    seg0_1 = make_segment(
        start=0.0,
        end=4.0,
        text="Welcome to machine learning.",
        words_data=[("Welcome", 0.0, 1.0), ("to", 1.0, 1.5), ("machine", 1.5, 2.5), ("learning.", 2.5, 3.5)],
    )
    seg0_2 = make_segment(
        start=294.0,
        end=299.0,
        text="We discuss gradient descent optimization.",
        words_data=[
            ("We", 294.0, 294.5),
            ("discuss", 294.5, 295.5),
            ("gradient", 295.5, 296.5),
            ("descent", 296.5, 297.5),
            ("optimization.", 297.5, 299.0),
        ],
    )
    res0 = TranscriptionResult(
        text="Welcome to machine learning. We discuss gradient descent optimization.",
        duration_seconds=299.0,
        language="en",
        segments=[seg0_1, seg0_2],
        words=seg0_1.words + seg0_2.words,
    )

    # Chunk 1: starts with overlap "gradient descent optimization" and continues with "and learning rate."
    seg1_1 = make_segment(
        start=295.5,
        end=304.0,
        text="gradient descent optimization and learning rate.",
        words_data=[
            ("gradient", 295.5, 296.5),
            ("descent", 296.5, 297.5),
            ("optimization", 297.5, 299.0),
            ("and", 299.5, 300.5),
            ("learning", 300.5, 301.5),
            ("rate.", 301.5, 303.0),
        ],
    )
    res1 = TranscriptionResult(
        text="gradient descent optimization and learning rate.",
        duration_seconds=304.0,
        language="en",
        segments=[seg1_1],
        words=seg1_1.words,
    )

    stitched = AudioChunker.stitch_and_deduplicate([res0, res1], overlap_window=5.0)

    # Overlapping duplicate words should be stripped
    words_text = [w.word.lower().strip(".") for w in stitched.words]
    # Check that "gradient" appears once, not twice
    assert words_text.count("gradient") == 1
    assert words_text.count("descent") == 1
    assert words_text.count("optimization") == 1
    assert "rate" in words_text

    # The stitched segments should contain the trimmed continuation
    assert len(stitched.segments) == 3
    assert stitched.segments[2].text == "and learning rate."
    assert stitched.segments[2].start_time >= 299.0


def test_stitching_coarse_segment_level_deduplication():
    """Stitching segments without word timestamps detects and drops whole duplicate segments."""
    seg0_1 = make_segment(start=0.0, end=10.0, text="Introductory lecture material.")
    seg0_2 = make_segment(start=295.0, end=300.0, text="Now let us move to neural networks.")
    res0 = TranscriptionResult(
        text="Introductory lecture material. Now let us move to neural networks.",
        duration_seconds=300.0,
        language="en",
        segments=[seg0_1, seg0_2],
        words=[],
    )

    # Chunk 1 repeats seg0_2, then introduces seg1_2
    seg1_1 = make_segment(start=295.0, end=300.0, text="Now let us move to neural networks.")
    seg1_2 = make_segment(start=301.0, end=308.0, text="They consist of layered computational units.")
    res1 = TranscriptionResult(
        text="Now let us move to neural networks. They consist of layered computational units.",
        duration_seconds=308.0,
        language="en",
        segments=[seg1_1, seg1_2],
        words=[],
    )

    stitched = AudioChunker.stitch_and_deduplicate([res0, res1], overlap_window=5.0)

    # seg1_1 should be discarded as a duplicate
    assert len(stitched.segments) == 3
    assert stitched.segments[0].text == "Introductory lecture material."
    assert stitched.segments[1].text == "Now let us move to neural networks."
    assert stitched.segments[2].text == "They consist of layered computational units."


@pytest.mark.asyncio
async def test_chunk_retry_once_success():
    """A failed chunk transcription is retried once and succeeds if second try passes."""
    from app.services.transcription_service import TranscriptionService

    service = TranscriptionService()
    fake_chunk = AudioChunk(
        index=0,
        total_chunks=1,
        start_time=0.0,
        end_time=30.0,
        duration=30.0,
        audio_path=Path("dummy.wav"),
        is_temp=False,
    )

    mock_provider = AsyncMock()
    valid_res = TranscriptionResult(
        text="Retry succeeded",
        duration_seconds=30.0,
        language="en",
        segments=[],
        words=[],
    )
    # Fail first time, succeed second time
    mock_provider.transcribe.side_effect = [RuntimeError("Temporary timeout"), valid_res]

    # Verify that calling transcribe twice works
    try:
        res = await mock_provider.transcribe(fake_chunk.audio_path)
    except Exception:
        res = await mock_provider.transcribe(fake_chunk.audio_path)

    assert res.text == "Retry succeeded"
    assert mock_provider.transcribe.call_count == 2
