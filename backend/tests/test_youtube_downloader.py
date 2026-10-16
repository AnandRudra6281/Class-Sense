from pathlib import Path
import pytest
from app.core.errors import MediaProcessingError
from app.services.youtube_downloader import YouTubeDownloader, youtube_downloader


def test_youtube_url_validation():
    valid_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
    ]
    for url in valid_urls:
        assert YouTubeDownloader.is_valid_url(url) is True
        assert YouTubeDownloader.extract_video_id(url) == "dQw4w9WgXcQ"


def test_youtube_url_invalid():
    invalid_urls = [
        "",
        "https://vimeo.com/123456",
        "https://google.com",
        "not-a-url",
        "https://youtube.com/watch?v=short",  # Invalid length (not 11 chars)
    ]
    for url in invalid_urls:
        assert YouTubeDownloader.is_valid_url(url) is False
        assert YouTubeDownloader.extract_video_id(url) is None


@pytest.mark.asyncio
async def test_download_media_invalid_url_raises_error():
    with pytest.raises(MediaProcessingError) as exc_info:
        await youtube_downloader.download_media("https://invalid-url.com/xyz")
    assert "invalid youtube url" in str(exc_info.value).lower()
