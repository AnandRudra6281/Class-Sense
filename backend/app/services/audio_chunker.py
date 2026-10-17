import asyncio
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from app.core.config import settings
from app.core.errors import AppException, AudioExtractionError
from app.schemas.transcript import (
    TranscriptionResult,
    TranscriptSegmentSchema,
    WordTimestamp,
)

logger = logging.getLogger("classsense.audio_chunker")


@dataclass
class AudioChunk:
    """Represents a time-slice chunk of an audio file."""
    index: int
    total_chunks: int
    start_time: float
    end_time: float
    duration: float
    audio_path: Path
    is_temp: bool = False


class AudioChunker:
    """Handles audio chunking, timestamp offsetting, and overlap de-duplication."""

    def __init__(
        self,
        chunk_duration_sec: float = 300.0,
        overlap_sec: float = 5.0,
        ffmpeg_bin: str = "ffmpeg",
    ):
        self.chunk_duration_sec = chunk_duration_sec
        self.overlap_sec = overlap_sec
        self.ffmpeg_bin = ffmpeg_bin

    def plan_chunks(
        self,
        total_duration: float,
        chunk_duration: Optional[float] = None,
        overlap: Optional[float] = None,
    ) -> List[Tuple[int, float, float]]:
        """
        Plans chunk windows [(index, start_time, duration), ...] given total duration.
        If total_duration <= chunk_duration, returns a single chunk covering [0, total_duration].
        """
        c_dur = chunk_duration or self.chunk_duration_sec
        c_ovlp = overlap or self.overlap_sec

        if total_duration <= 0:
            return [(0, 0.0, 0.0)]

        if total_duration <= c_dur:
            return [(0, 0.0, total_duration)]

        step = max(1.0, c_dur - c_ovlp)
        chunks: List[Tuple[int, float, float]] = []
        start = 0.0
        idx = 0

        while start < total_duration:
            duration = min(c_dur, total_duration - start)
            chunks.append((idx, start, duration))
            if start + duration >= total_duration:
                break
            start += step
            idx += 1

        return chunks

    async def extract_chunk_file(
        self,
        source_audio: Path,
        start_time: float,
        duration: float,
        output_path: Path,
    ) -> None:
        """Extracts a slice from source_audio using ffmpeg to 16kHz mono WAV."""
        if not shutil.which(self.ffmpeg_bin):
            raise AudioExtractionError(f"ffmpeg executable '{self.ffmpeg_bin}' not found on system PATH.")

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-ss",
            f"{start_time:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source_audio),
            "-c:a",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ]

        logger.debug(f"Running ffmpeg chunk extraction: {' '.join(cmd)}")
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            raise AudioExtractionError(f"ffmpeg chunk extraction failed (code {proc.returncode}): {err}")

    async def split_audio_into_chunks(
        self,
        audio_path: Path,
        total_duration: float,
        temp_dir: Optional[Path] = None,
        chunk_duration: Optional[float] = None,
        overlap: Optional[float] = None,
    ) -> List[AudioChunk]:
        """
        Splits an audio file into ~5 minute chunks with ~5s overlap.
        If total_duration <= chunk_duration, returns the original file as a single chunk.
        """
        plan = self.plan_chunks(total_duration, chunk_duration, overlap)
        if len(plan) <= 1:
            return [
                AudioChunk(
                    index=0,
                    total_chunks=1,
                    start_time=0.0,
                    end_time=total_duration,
                    duration=total_duration,
                    audio_path=audio_path,
                    is_temp=False,
                )
            ]

        # Multiple chunks needed
        target_dir = temp_dir or Path(tempfile.mkdtemp(prefix="audio_chunks_"))
        target_dir.mkdir(parents=True, exist_ok=True)

        chunks: List[AudioChunk] = []
        total_chunks = len(plan)

        for idx, start, dur in plan:
            out_file = target_dir / f"chunk_{idx:04d}_{start:.1f}_{dur:.1f}.wav"
            await self.extract_chunk_file(audio_path, start, dur, out_file)
            chunks.append(
                AudioChunk(
                    index=idx,
                    total_chunks=total_chunks,
                    start_time=start,
                    end_time=start + dur,
                    duration=dur,
                    audio_path=out_file,
                    is_temp=True,
                )
            )

        return chunks

    @staticmethod
    def offset_transcription_result(
        result: TranscriptionResult,
        offset_seconds: float,
    ) -> TranscriptionResult:
        """Applies a time offset in seconds to all segments and words in a TranscriptionResult."""
        if offset_seconds == 0.0:
            return result

        offset_segments: List[TranscriptSegmentSchema] = []
        for seg in result.segments:
            seg_dict = seg.model_dump()
            seg_dict["start_time"] = round(seg_dict["start_time"] + offset_seconds, 3)
            seg_dict["end_time"] = round(seg_dict["end_time"] + offset_seconds, 3)

            new_words = []
            for w in seg_dict.get("words", []):
                new_words.append(
                    WordTimestamp(
                        word=w["word"],
                        start=round(w["start"] + offset_seconds, 3),
                        end=round(w["end"] + offset_seconds, 3),
                        probability=w.get("probability"),
                    )
                )
            seg_dict["words"] = new_words
            offset_segments.append(TranscriptSegmentSchema(**seg_dict))

        offset_words: List[WordTimestamp] = []
        for w in result.words:
            offset_words.append(
                WordTimestamp(
                    word=w.word,
                    start=round(w.start + offset_seconds, 3),
                    end=round(w.end + offset_seconds, 3),
                    probability=w.probability,
                )
            )

        return TranscriptionResult(
            text=result.text,
            duration_seconds=result.duration_seconds,
            language=result.language,
            segments=offset_segments,
            words=offset_words,
        )

    @classmethod
    def stitch_and_deduplicate(
        cls,
        chunk_results: List[TranscriptionResult],
        overlap_window: float = 5.0,
    ) -> TranscriptionResult:
        """
        Stitches multiple chunk transcription results with offset timestamps and
        de-duplicates overlapping words and segments in transition boundaries.
        """
        if not chunk_results:
            return TranscriptionResult(
                text="",
                duration_seconds=0.0,
                language="en",
                segments=[],
                words=[],
            )

        if len(chunk_results) == 1:
            return chunk_results[0]

        stitched_segments: List[TranscriptSegmentSchema] = []
        stitched_words: List[WordTimestamp] = []
        detected_language = chunk_results[0].language

        # Initialize with first chunk
        first_chunk = chunk_results[0]
        stitched_segments.extend(first_chunk.segments)
        stitched_words.extend(first_chunk.words)

        for chunk_idx in range(1, len(chunk_results)):
            curr_chunk = chunk_results[chunk_idx]
            if not curr_chunk.segments:
                continue

            if not stitched_segments:
                stitched_segments.extend(curr_chunk.segments)
                stitched_words.extend(curr_chunk.words)
                continue

            prev_max_end = max(s.end_time for s in stitched_segments)

            # Check if word-level deduplication is possible
            has_prev_words = bool(stitched_words)
            has_curr_words = any(bool(s.words) for s in curr_chunk.segments)

            if has_prev_words and has_curr_words:
                cls._stitch_words(
                    stitched_segments=stitched_segments,
                    stitched_words=stitched_words,
                    incoming_segments=curr_chunk.segments,
                    prev_max_end=prev_max_end,
                    overlap_window=overlap_window,
                )
            else:
                cls._stitch_segments_coarse(
                    stitched_segments=stitched_segments,
                    stitched_words=stitched_words,
                    incoming_segments=curr_chunk.segments,
                    prev_max_end=prev_max_end,
                )

        # Re-derive full combined text and duration
        combined_text = " ".join(s.text.strip() for s in stitched_segments if s.text.strip())
        max_duration = max((s.end_time for s in stitched_segments), default=0.0)

        # Synchronize stitched_words if segments have words
        all_words: List[WordTimestamp] = []
        for s in stitched_segments:
            all_words.extend(s.words)
        if not all_words and stitched_words:
            all_words = stitched_words

        return TranscriptionResult(
            text=combined_text,
            duration_seconds=round(max_duration, 3),
            language=detected_language,
            segments=stitched_segments,
            words=all_words,
        )

    @staticmethod
    def _normalize_token(text: str) -> str:
        """Strips punctuation and lowercases for fuzzy token comparison."""
        return re.sub(r"[^\w]", "", text).lower().strip()

    @classmethod
    def _stitch_words(
        cls,
        stitched_segments: List[TranscriptSegmentSchema],
        stitched_words: List[WordTimestamp],
        incoming_segments: List[TranscriptSegmentSchema],
        prev_max_end: float,
        overlap_window: float,
    ) -> None:
        """Word-level alignment and de-duplication across chunk boundaries."""
        # Consider words in the overlap zone
        recent_cutoff = prev_max_end - overlap_window - 2.0
        recent_prev_words = [w for w in stitched_words if w.start >= recent_cutoff]
        if not recent_prev_words:
            recent_prev_words = stitched_words[-15:]

        incoming_words: List[WordTimestamp] = []
        for s in incoming_segments:
            incoming_words.extend(s.words)

        candidate_incoming_words = [
            w for w in incoming_words if w.start <= prev_max_end + 2.0
        ]

        prev_tokens = [cls._normalize_token(w.word) for w in recent_prev_words]
        next_tokens = [cls._normalize_token(w.word) for w in candidate_incoming_words]

        # Find longest suffix-prefix match
        match_len = 0
        max_search = min(len(prev_tokens), len(next_tokens))
        for L in range(max_search, 0, -1):
            if prev_tokens[-L:] == next_tokens[:L]:
                # Verify timestamp delta is reasonable
                time_delta = abs(recent_prev_words[-L].start - candidate_incoming_words[0].start)
                if time_delta <= overlap_window + 3.0:
                    match_len = L
                    break

        # Duplicate cutoff
        dup_cutoff_time = -1.0
        if match_len > 0:
            dup_cutoff_time = candidate_incoming_words[match_len - 1].end
        else:
            # If no exact word sequence matched, fallback to time cutoff
            dup_cutoff_time = prev_max_end

        # Now process incoming segments and strip duplicate words/segments
        for seg in incoming_segments:
            # If segment has words, filter out words occurring before or at dup_cutoff_time
            if seg.words:
                remaining_words = [
                    w for w in seg.words
                    if w.end > dup_cutoff_time and w.start >= (dup_cutoff_time - 0.2)
                ]
                if not remaining_words:
                    # Entire segment is within the duplicate overlap
                    continue

                new_start = remaining_words[0].start
                new_end = remaining_words[-1].end
                new_text = " ".join(w.word for w in remaining_words).strip()

                seg_dict = seg.model_dump()
                seg_dict["start_time"] = new_start
                seg_dict["end_time"] = new_end
                seg_dict["text"] = new_text
                seg_dict["words"] = remaining_words

                cleaned_seg = TranscriptSegmentSchema(**seg_dict)
                stitched_segments.append(cleaned_seg)
                stitched_words.extend(remaining_words)
            else:
                # Segment without word timestamps
                if seg.end_time <= dup_cutoff_time:
                    continue
                seg_dict = seg.model_dump()
                seg_dict["start_time"] = max(seg.start_time, dup_cutoff_time)
                stitched_segments.append(TranscriptSegmentSchema(**seg_dict))

    @classmethod
    def _stitch_segments_coarse(
        cls,
        stitched_segments: List[TranscriptSegmentSchema],
        stitched_words: List[WordTimestamp],
        incoming_segments: List[TranscriptSegmentSchema],
        prev_max_end: float,
    ) -> None:
        """Segment-level de-duplication when word-level timestamps are unavailable."""
        prev_tail_text = " ".join(s.text for s in stitched_segments[-3:]).lower()

        for seg in incoming_segments:
            # If segment ends before previous audio end, check for duplicate text
            if seg.end_time <= prev_max_end:
                norm_text = cls._normalize_token(seg.text)
                if norm_text and norm_text in cls._normalize_token(prev_tail_text):
                    continue  # Exact duplicate segment

            # If segment starts before previous end
            if seg.start_time < prev_max_end:
                seg_words = seg.text.split()
                # Find if prefix matches tail of previous text
                matched_prefix = 0
                for k in range(len(seg_words), 0, -1):
                    cand = cls._normalize_token(" ".join(seg_words[:k]))
                    if cand and cand in cls._normalize_token(prev_tail_text):
                        matched_prefix = k
                        break

                remaining_words = seg_words[matched_prefix:]
                if not remaining_words:
                    continue  # All words in segment duplicate

                seg_dict = seg.model_dump()
                seg_dict["start_time"] = max(seg.start_time, prev_max_end)
                seg_dict["text"] = " ".join(remaining_words)
                stitched_segments.append(TranscriptSegmentSchema(**seg_dict))
            else:
                stitched_segments.append(seg)
