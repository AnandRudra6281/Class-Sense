import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.errors import MediaProcessingError

logger = logging.getLogger("classsense.youtube_downloader")

YOUTUBE_URL_REGEX = re.compile(
    r"^(https?://)?(www\.|m\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})(&.*)?$"
)


class YouTubeDownloader:
    """Service to validate and download YouTube lecture videos/audio streams via yt-dlp."""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validates if string is a recognized YouTube video or short URL."""
        if not url:
            return False
        return bool(YOUTUBE_URL_REGEX.match(url.strip()))

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """Extracts the 11-character video ID from a YouTube URL."""
        match = YOUTUBE_URL_REGEX.match(url.strip())
        if match:
            return match.group(4)
        return None

    async def download_media(self, url: str, target_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Downloads the best audio stream of the YouTube video using yt-dlp.
        Returns a dictionary with file_path, title, duration, and video_id.
        """
        if not self.is_valid_url(url):
            raise MediaProcessingError(
                f"Invalid YouTube URL: '{url}'. Please provide a standard watch or youtu.be URL.",
                details={"url": url},
            )

        destination_dir = target_dir or settings.raw_upload_dir
        destination_dir.mkdir(parents=True, exist_ok=True)

        return await asyncio.to_thread(self._sync_download, url, destination_dir)

    def _sync_download(self, url: str, destination_dir: Path) -> Dict[str, Any]:
        try:
            import yt_dlp
        except ImportError:
            raise MediaProcessingError("yt-dlp is not installed in the python environment.")

        video_id = self.extract_video_id(url) or "video"
        out_tmpl = str(destination_dir / f"yt_{video_id}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_tmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    raise MediaProcessingError("Failed to extract info from YouTube URL.")

                downloaded_file = Path(ydl.prepare_filename(info))

                # Handle post-processing extension changes if any
                if not downloaded_file.exists():
                    # Check if file with same stem exists in destination_dir
                    candidates = list(destination_dir.glob(f"yt_{video_id}.*"))
                    if candidates:
                        downloaded_file = candidates[0]
                    else:
                        raise MediaProcessingError(f"Downloaded file not found at expected path: {downloaded_file}")

                return {
                    "file_path": downloaded_file,
                    "title": info.get("title", f"YouTube Lecture ({video_id})"),
                    "duration_seconds": float(info.get("duration", 0.0)),
                    "video_id": video_id,
                    "channel": info.get("channel") or info.get("uploader", "Unknown"),
                    "thumbnail": info.get("thumbnail"),
                }
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp download failed for {url}: {e}")
            raise MediaProcessingError(f"Failed to download YouTube video: {str(e)}", details={"url": url})
        except Exception as e:
            logger.error(f"Unexpected error downloading YouTube video {url}: {e}", exc_info=True)
            raise MediaProcessingError(f"Error during YouTube media ingestion: {str(e)}", details={"url": url})


youtube_downloader = YouTubeDownloader()
