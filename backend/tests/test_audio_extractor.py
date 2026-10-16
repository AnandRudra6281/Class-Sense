import asyncio
from pathlib import Path
import pytest
from app.core.errors import AudioExtractionError, MediaProcessingError
from app.services.audio_extractor import AudioExtractor


@pytest.fixture
def extractor():
    return AudioExtractor()


@pytest.fixture
async def sample_stereo_wav(tmp_path: Path) -> Path:
    """Creates a small 2-second 44.1kHz stereo test WAV file using ffmpeg."""
    input_file = tmp_path / "synthetic_stereo.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=2",
        "-ar",
        "44100",
        "-ac",
        "2",
        str(input_file),
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()
    assert input_file.exists() and input_file.stat().st_size > 0
    return input_file


@pytest.mark.asyncio
async def test_probe_metadata_returns_accurate_audio_info(extractor: AudioExtractor, sample_stereo_wav: Path):
    meta = await extractor.probe_metadata(sample_stereo_wav)
    assert meta["has_audio"] is True
    assert 1.8 <= meta["duration_seconds"] <= 2.2
    assert meta["channels"] == 2
    assert meta["sample_rate"] == 44100


@pytest.mark.asyncio
async def test_extract_16k_mono_wav_converts_properly(extractor: AudioExtractor, sample_stereo_wav: Path, tmp_path: Path):
    output_wav = tmp_path / "converted_16k_mono.wav"
    res = await extractor.extract_16k_mono_wav(sample_stereo_wav, output_wav)

    assert res == output_wav
    assert output_wav.exists()
    assert output_wav.stat().st_size > 0

    # Probe converted file to verify 16kHz mono specification
    converted_meta = await extractor.probe_metadata(output_wav)
    assert converted_meta["has_audio"] is True
    assert converted_meta["channels"] == 1
    assert converted_meta["sample_rate"] == 16000
    assert 1.8 <= converted_meta["duration_seconds"] <= 2.2


@pytest.mark.asyncio
async def test_probe_nonexistent_file_raises_error(extractor: AudioExtractor, tmp_path: Path):
    fake_path = tmp_path / "nonexistent.mp4"
    with pytest.raises(MediaProcessingError) as exc_info:
        await extractor.probe_metadata(fake_path)
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_extract_nonexistent_file_raises_error(extractor: AudioExtractor, tmp_path: Path):
    fake_path = tmp_path / "ghost.wav"
    with pytest.raises(MediaProcessingError):
        await extractor.extract_16k_mono_wav(fake_path)
