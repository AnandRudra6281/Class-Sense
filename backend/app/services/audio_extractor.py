import asyncio
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.errors import AudioExtractionError, MediaProcessingError

logger = logging.getLogger("classsense.audio_extractor")


class AudioExtractor:
    """Service for media probing and 16kHz mono PCM WAV extraction via ffmpeg."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"):
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self._verify_bins()

    def _verify_bins(self) -> None:
        """Verifies that ffmpeg and ffprobe are available on system PATH."""
        if not shutil.which(self.ffmpeg_bin):
            logger.warning(f"ffmpeg executable '{self.ffmpeg_bin}' was not found in PATH.")
        if not shutil.which(self.ffprobe_bin):
            logger.warning(f"ffprobe executable '{self.ffprobe_bin}' was not found in PATH.")

    async def probe_metadata(self, media_path: Path) -> Dict[str, Any]:
        """Probes media container and stream metadata using ffprobe."""
        if not media_path.exists():
            raise MediaProcessingError(f"Media file not found: {media_path}")

        cmd = [
            self.ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name,bit_rate,size",
            "-show_entries",
            "stream=index,codec_name,codec_type,sample_rate,channels",
            "-of",
            "json",
            str(media_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                logger.warning(f"ffprobe returned non-zero code {proc.returncode}: {err_msg}. Attempting fallback probe.")
                return await self._probe_fallback_ffmpeg(media_path)

            data = json.loads(stdout.decode("utf-8", errors="replace"))
            fmt = data.get("format", {})
            duration_str = fmt.get("duration")
            duration = float(duration_str) if duration_str is not None else 0.0

            audio_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
                None,
            )

            return {
                "duration_seconds": duration,
                "format_name": fmt.get("format_name", "unknown"),
                "size_bytes": int(fmt.get("size", media_path.stat().st_size)),
                "bit_rate": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None,
                "sample_rate": int(audio_stream.get("sample_rate", 0)) if audio_stream and audio_stream.get("sample_rate") else None,
                "channels": int(audio_stream.get("channels", 0)) if audio_stream and audio_stream.get("channels") else None,
                "has_audio": audio_stream is not None,
            }
        except Exception as e:
            logger.warning(f"Error during ffprobe metadata inspection: {e}. Trying fallback.")
            return await self._probe_fallback_ffmpeg(media_path)

    async def _probe_fallback_ffmpeg(self, media_path: Path) -> Dict[str, Any]:
        """Fallback duration probe by parsing ffmpeg stderr output."""
        cmd = [self.ffmpeg_bin, "-i", str(media_path)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        stderr_str = stderr.decode("utf-8", errors="replace")

        # Duration pattern: Duration: 00:01:23.45
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr_str)
        if match:
            hours, minutes, seconds = match.groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        else:
            duration = 0.0

        has_audio = "Audio:" in stderr_str

        return {
            "duration_seconds": duration,
            "format_name": media_path.suffix.lstrip(".").lower(),
            "size_bytes": media_path.stat().st_size,
            "bit_rate": None,
            "sample_rate": 16000 if has_audio else None,
            "channels": 1 if has_audio else None,
            "has_audio": has_audio,
        }

    async def extract_16k_mono_wav(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Extracts media audio to 16kHz mono 16-bit PCM WAV using ffmpeg.
        This audio specification matches the standard requirement for Voxtral and Whisper ASR.
        """
        if not input_path.exists():
            raise MediaProcessingError(f"Input media file does not exist: {input_path}")

        if output_path is None:
            output_dir = settings.audio_upload_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{input_path.stem}_16k_mono.wav"
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_bin,
            "-y",  # Overwrite output without asking
            "-i",
            str(input_path),
            "-vn",  # Disable video stream
            "-acodec",
            "pcm_s16le",  # 16-bit PCM
            "-ar",
            "16000",  # 16kHz sample rate
            "-ac",
            "1",  # Mono channel
            str(output_path),
        ]

        logger.info(f"Extracting audio via ffmpeg: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_text = stderr.decode("utf-8", errors="replace").strip()
            logger.error(f"ffmpeg extraction failed with code {proc.returncode}: {err_text}")
            raise AudioExtractionError(
                f"Failed to extract 16kHz mono audio from media: {err_text}",
                details={"input": str(input_path), "output": str(output_path), "code": proc.returncode},
            )

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise AudioExtractionError(
                "ffmpeg completed but generated an empty or non-existent audio file.",
                details={"output": str(output_path)},
            )

        logger.info(f"Successfully extracted audio to: {output_path} ({output_path.stat().st_size} bytes)")
        return output_path


audio_extractor = AudioExtractor()
